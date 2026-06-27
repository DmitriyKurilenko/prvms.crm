from __future__ import annotations

import json
import uuid

from django.utils import timezone
from django_tenants.utils import schema_context

from apps.tenants.models import Domain, Tenant
from apps.users.models import Membership, User

from .base import TenantAPITestCase


class InviteFlowAPITest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='invite_owner@example.com', username='invite_owner')
        self.owner.set_password('ownerpass123')
        self.owner.save(update_fields=['password'])

    def _invite(self, email: str, role: str = 'manager'):
        headers = self.auth_headers(self.owner, host='localhost')
        return self.client.post(
            '/api/users/invite',
            data=json.dumps({'email': email, 'role': role}),
            content_type='application/json',
            **headers,
        )

    def _create_tenant(self, slug_prefix: str, role_for_owner: str | None = None):
        slug = f'{slug_prefix}-{uuid.uuid4().hex[:6]}'
        with schema_context('public'):
            tenant = Tenant.objects.create(
                schema_name=slug,
                slug=slug,
                name=f'Tenant {slug}',
                plan=self.tenant.plan,
                is_active=True,
                is_paid=True,
            )
            Domain.objects.create(
                tenant=tenant,
                domain=f'{slug}.localhost',
                is_primary=True,
            )
            if role_for_owner:
                Membership.objects.create(
                    user=self.owner,
                    tenant=tenant,
                    role=role_for_owner,
                    is_active=True,
                    joined_at=timezone.now(),
                )
        return tenant

    def test_invite_new_user_and_accept(self):
        email = 'new_invited_user@example.com'
        invite_response = self._invite(email=email, role='manager')
        self.assertEqual(invite_response.status_code, 201)

        payload = invite_response.json()
        token = payload['invite_token']
        self.assertIn('/invite/accept?token=', payload['invite_link'])

        with schema_context('public'):
            membership = Membership.objects.select_related('user').get(tenant=self.tenant, user__email=email)
            self.assertEqual(membership.role, 'manager')
            self.assertTrue(membership.is_active)
            self.assertIsNotNone(membership.invite_token)
            self.assertIsNone(membership.joined_at)

        check_response = self.client.get('/api/auth/invite/check', {'token': token}, HTTP_HOST='localhost')
        self.assertEqual(check_response.status_code, 200)
        self.assertFalse(check_response.json()['has_account'])

        accept_response = self.client.post(
            '/api/auth/invite/accept',
            data=json.dumps({'token': token, 'password': 'NewUserPass123', 'username': 'new_invited_user'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(accept_response.status_code, 200)
        self.assertEqual(accept_response.json()['tenant_slug'], self.tenant.slug)

        with schema_context('public'):
            membership.refresh_from_db()
            self.assertIsNone(membership.invite_token)
            self.assertIsNotNone(membership.joined_at)
            self.assertTrue(membership.user.has_usable_password())

    def test_invite_existing_user_requires_password_on_accept(self):
        with schema_context('public'):
            existing = User.objects.create_user(
                email='existing_invited@example.com',
                username='existing_invited',
                password='ExistingPass123',
            )
        invite_response = self._invite(email=existing.email, role='admin')
        self.assertEqual(invite_response.status_code, 201)
        token = invite_response.json()['invite_token']

        no_password_response = self.client.post(
            '/api/auth/invite/accept',
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(no_password_response.status_code, 400)

        wrong_password_response = self.client.post(
            '/api/auth/invite/accept',
            data=json.dumps({'token': token, 'password': 'WrongPass'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(wrong_password_response.status_code, 400)

        ok_response = self.client.post(
            '/api/auth/invite/accept',
            data=json.dumps({'token': token, 'password': 'ExistingPass123'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(ok_response.json()['tenant_slug'], self.tenant.slug)

        with schema_context('public'):
            membership = Membership.objects.get(user=existing, tenant=self.tenant)
            self.assertIsNone(membership.invite_token)
            self.assertIsNotNone(membership.joined_at)
            self.assertEqual(membership.role, 'admin')

    def test_auth_organizations_and_switch_tenant(self):
        second_tenant = self._create_tenant('qa-org-switch', role_for_owner='manager')
        try:
            login = self.client.post(
                '/api/auth/login',
                data=json.dumps({'email': self.owner.email, 'password': 'ownerpass123'}),
                content_type='application/json',
                HTTP_HOST='localhost',
            )
            self.assertEqual(login.status_code, 200)
            token = login.json()['access_token']

            organizations = self.client.get(
                '/api/auth/organizations',
                HTTP_HOST='localhost',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(organizations.status_code, 200)
            slugs = {item['tenant_slug'] for item in organizations.json()}
            self.assertIn(self.tenant.slug, slugs)
            self.assertIn(second_tenant.slug, slugs)

            switch = self.client.post(
                '/api/auth/switch-tenant',
                data=json.dumps({'tenant_slug': second_tenant.slug}),
                content_type='application/json',
                HTTP_HOST='localhost',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(switch.status_code, 200)
            self.assertEqual(switch.json()['tenant_slug'], second_tenant.slug)
            switched_token = switch.json()['access_token']

            me = self.client.get(
                '/api/auth/me',
                HTTP_HOST='localhost',
                HTTP_X_TENANT_SLUG=second_tenant.slug,
                HTTP_AUTHORIZATION=f'Bearer {switched_token}',
            )
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()['tenant_slug'], second_tenant.slug)
            self.assertEqual(me.json()['role'], 'manager')
        finally:
            with schema_context('public'):
                tenant = Tenant.objects.filter(id=second_tenant.id).first()
                if tenant:
                    tenant.delete(force_drop=True)

    def test_login_default_tenant_ignores_pending_invites(self):
        second_tenant = self._create_tenant('qa-org-pending')
        try:
            with schema_context('public'):
                Membership.objects.create(
                    user=self.owner,
                    tenant=second_tenant,
                    role='admin',
                    is_active=True,
                    invite_token=uuid.uuid4(),
                    invited_at=timezone.now(),
                    joined_at=None,
                )

            response = self.client.post(
                '/api/auth/login',
                data=json.dumps({'email': self.owner.email, 'password': 'ownerpass123'}),
                content_type='application/json',
                HTTP_HOST='localhost',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['tenant_slug'], self.tenant.slug)
        finally:
            with schema_context('public'):
                tenant = Tenant.objects.filter(id=second_tenant.id).first()
                if tenant:
                    tenant.delete(force_drop=True)

    def test_switch_tenant_requires_active_membership(self):
        second_tenant = self._create_tenant('qa-org-forbidden')
        try:
            login = self.client.post(
                '/api/auth/login',
                data=json.dumps({'email': self.owner.email, 'password': 'ownerpass123'}),
                content_type='application/json',
                HTTP_HOST='localhost',
            )
            self.assertEqual(login.status_code, 200)
            token = login.json()['access_token']

            response = self.client.post(
                '/api/auth/switch-tenant',
                data=json.dumps({'tenant_slug': second_tenant.slug}),
                content_type='application/json',
                HTTP_HOST='localhost',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 403)
        finally:
            with schema_context('public'):
                tenant = Tenant.objects.filter(id=second_tenant.id).first()
                if tenant:
                    tenant.delete(force_drop=True)

    def test_legacy_empty_password_user_is_treated_as_new_account_on_accept(self):
        with schema_context('public'):
            legacy_user = User.objects.create(
                email='legacy_blank_pass@example.com',
                username='legacy_blank_pass',
                password='',
            )
        invite_response = self._invite(email=legacy_user.email, role='manager')
        self.assertEqual(invite_response.status_code, 201)
        token = invite_response.json()['invite_token']

        check_response = self.client.get('/api/auth/invite/check', {'token': token}, HTTP_HOST='localhost')
        self.assertEqual(check_response.status_code, 200)
        self.assertFalse(check_response.json()['has_account'])

        accept_response = self.client.post(
            '/api/auth/invite/accept',
            data=json.dumps({'token': token, 'password': 'LegacyPass123', 'username': 'legacy_fixed'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(accept_response.status_code, 200)

        with schema_context('public'):
            legacy_user.refresh_from_db()
            self.assertTrue(legacy_user.has_usable_password())
