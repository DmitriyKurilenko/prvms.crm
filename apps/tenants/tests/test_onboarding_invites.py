from __future__ import annotations

import json

from django_tenants.utils import schema_context, tenant_context

from apps.integrations.models import ManagerProfile
from apps.users.models import Membership
from apps.users.tests.base import TenantAPITestCase


class OnboardingInviteTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='owner_onboarding@example.com', username='owner_onboarding')
        self.owner.set_password('ownerpass123')
        self.owner.save(update_fields=['password'])

    def test_step_3_creates_pending_invite_membership_for_manager_email(self):
        headers = self.auth_headers(self.owner, host='localhost')
        email = 'manager_from_onboarding@example.com'

        response = self.client.post(
            '/api/onboarding/step/3/',
            data=json.dumps({'managers': [{'name': 'Manager One', 'email': email}]}),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(response.status_code, 200)

        with schema_context('public'):
            membership = Membership.objects.select_related('user').get(
                tenant_id=self.tenant.id,
                user__email=email,
                is_active=True,
            )
            self.assertEqual(membership.role, 'manager')
            self.assertIsNotNone(membership.invite_token)
            self.assertIsNotNone(membership.invited_at)
            self.assertIsNone(membership.joined_at)
            self.assertFalse(membership.user.has_usable_password())

        check = self.client.get('/api/auth/invite/check', {'token': str(membership.invite_token)}, HTTP_HOST='localhost')
        self.assertEqual(check.status_code, 200)
        self.assertFalse(check.json()['has_account'])

        with tenant_context(self.tenant):
            self.assertTrue(ManagerProfile.objects.filter(user__email=email).exists())
