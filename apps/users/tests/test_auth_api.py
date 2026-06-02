from __future__ import annotations

import json
import uuid

from django_tenants.utils import schema_context

from apps.tenants.models import Tenant
from apps.users.models import Membership

from .base import TenantAPITestCase


class AuthAPITest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='owner_auth@example.com', username='owner_auth')
        self.owner.set_password('ownerpass123')
        self.owner.save(update_fields=['password'])

    def test_login_returns_tenant_slug(self):
        response = self.client.post(
            '/api/auth/login',
            data=json.dumps({'email': self.owner.email, 'password': 'ownerpass123'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('access_token', payload)
        self.assertEqual(payload.get('tenant_slug'), self.tenant.slug)

    def test_login_accepts_username_identifier(self):
        response = self.client.post(
            '/api/auth/login',
            data=json.dumps({'login': self.owner.username, 'password': 'ownerpass123'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('access_token', payload)
        self.assertEqual(payload.get('tenant_slug'), self.tenant.slug)

    def test_login_is_case_insensitive_for_email(self):
        response = self.client.post(
            '/api/auth/login',
            data=json.dumps({'email': self.owner.email.upper(), 'password': 'ownerpass123'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('access_token', payload)
        self.assertEqual(payload.get('tenant_slug'), self.tenant.slug)

    def test_refresh_returns_tenant_slug(self):
        login = self.client.post(
            '/api/auth/login',
            data=json.dumps({'email': self.owner.email, 'password': 'ownerpass123'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(login.status_code, 200)

        refresh = self.client.post('/api/auth/refresh', HTTP_HOST='localhost')
        self.assertEqual(refresh.status_code, 200)
        payload = refresh.json()
        self.assertIn('access_token', payload)
        self.assertEqual(payload.get('tenant_slug'), self.tenant.slug)

    def test_me_returns_role_and_tenant(self):
        headers = self.auth_headers(self.owner, host='localhost')
        response = self.client.get('/api/auth/me', **headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['role'], 'owner')
        self.assertEqual(payload['tenant_slug'], self.tenant.slug)
        self.assertEqual(payload['tenant_id'], self.tenant.id)

    def test_register_works_from_non_public_request_context(self):
        org_slug = f'qa-reg-{uuid.uuid4().hex[:8]}'
        email = f'{org_slug}@example.com'
        username = f'user_{org_slug}'
        created_tenant_id = None

        response = self.client.post(
            '/api/auth/register',
            data=json.dumps(
                {
                    'email': email,
                    'password': 'OwnerPass123',
                    'username': username,
                    'org_name': f'Org {org_slug}',
                    'org_slug': org_slug,
                    'plan_slug': 'komanda',
                }
            ),
            content_type='application/json',
            HTTP_HOST=self.get_test_tenant_domain(),
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['tenant_slug'], org_slug)

        try:
            with schema_context('public'):
                created_tenant = Tenant.objects.get(slug=org_slug)
                created_tenant_id = created_tenant.id
                membership = Membership.objects.get(tenant=created_tenant, user__email=email, is_active=True)
                self.assertEqual(membership.role, 'owner')

            me_response = self.client.get(
                '/api/auth/me',
                HTTP_HOST='localhost',
                HTTP_X_TENANT_SLUG=org_slug,
                HTTP_AUTHORIZATION=f"Bearer {payload['access_token']}",
            )
            self.assertEqual(me_response.status_code, 200)
            self.assertEqual(me_response.json()['tenant_slug'], org_slug)
        finally:
            if created_tenant_id:
                with schema_context('public'):
                    tenant = Tenant.objects.filter(id=created_tenant_id).first()
                    if tenant:
                        tenant.delete(force_drop=True)
