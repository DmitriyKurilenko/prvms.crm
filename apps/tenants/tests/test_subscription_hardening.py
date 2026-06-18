from __future__ import annotations

import json
import uuid
from datetime import timedelta

from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.documents.models import Document, DocumentTemplate
from apps.crm.models import Pipeline
from apps.integrations.models import CRMConnection
from apps.tenants.models import Tenant
from apps.users.models import Membership, User
from apps.users.tests.base import TenantAPITestCase


class SubscriptionHardeningTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='sub_owner@example.com', username='sub_owner')
        self.template = DocumentTemplate.objects.create(
            name='Subscription template',
            version=1,
            html_body='<p>{{ x }}</p>',
            variable_schema=[{'key': 'x', 'sample': '1'}],
            is_active=True,
        )

    def _headers(self):
        return self.auth_headers(self.owner, host='localhost')

    def _expire_trial(self):
        with schema_context('public'):
            tenant = Tenant.objects.get(id=self.tenant.id)
            tenant.is_paid = False
            tenant.trial_expires_at = timezone.now() - timedelta(days=1)
            tenant.save(update_fields=['is_paid', 'trial_expires_at'])

    def test_trial_expired_allows_subscription_endpoints_but_blocks_business_api(self):
        self._expire_trial()
        headers = self._headers()

        tenant_response = self.client.get('/api/tenant/', **headers)
        self.assertEqual(tenant_response.status_code, 200)

        plan_response = self.client.get('/api/tenant/plan/', **headers)
        self.assertEqual(plan_response.status_code, 200)
        self.assertIn('pipelines', plan_response.json()['usage'])

        plans_response = self.client.get('/api/tenant/plans/', **headers)
        self.assertEqual(plans_response.status_code, 200)

        payments_response = self.client.get('/api/billing/payments/', **headers)
        self.assertEqual(payments_response.status_code, 200)

        change_plan_response = self.client.post(
            '/api/billing/change-plan/',
            data=json.dumps({'plan_slug': 'solo'}),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(change_plan_response.status_code, 200)

        checkout_response = self.client.post(
            '/api/billing/checkout/',
            data=json.dumps({'plan_slug': 'solo', 'months': 1}),
            content_type='application/json',
            **headers,
        )
        self.assertNotEqual(checkout_response.status_code, 402)
        self.assertIn(checkout_response.status_code, [200, 400, 503])

        documents_response = self.client.get('/api/documents/', **headers)
        self.assertEqual(documents_response.status_code, 402)

    def test_tenant_plan_usage_uses_memberships_and_includes_pipelines(self):
        self.create_user(role='admin', email='usage_admin@example.com', username='usage_admin')
        self.create_user(role='manager', email='usage_manager@example.com', username='usage_manager')
        self.create_user(role='viewer', email='usage_viewer@example.com', username='usage_viewer')

        with schema_context('public'):
            inactive_user = User.objects.create_user(
                email='usage_inactive@example.com',
                username='usage_inactive',
                password='pass12345',
            )
            Membership.objects.create(
                user=inactive_user,
                tenant_id=self.tenant.id,
                role='manager',
                is_active=False,
                joined_at=timezone.now(),
            )
            pending_user = User.objects.create_user(
                email='usage_pending@example.com',
                username='usage_pending',
                password='pass12345',
            )
            Membership.objects.create(
                user=pending_user,
                tenant_id=self.tenant.id,
                role='manager',
                is_active=True,
                invite_token=uuid.uuid4(),
                invited_at=timezone.now(),
                joined_at=None,
            )

        with tenant_context(self.tenant):
            Pipeline.objects.create(name='Active pipeline', is_active=True)
            Pipeline.objects.create(name='Inactive pipeline', is_active=False)
            CRMConnection.objects.create(
                crm_type='amocrm',
                name='Active connection',
                credentials={'access_token': 'token'},
                is_active=True,
            )
            CRMConnection.objects.create(
                crm_type='bitrix24',
                name='Inactive connection',
                credentials={'webhook_url': 'https://example.com'},
                is_active=False,
            )
            Document.objects.create(
                template=self.template,
                template_version=1,
                crm_entity_type='manual',
                crm_entity_id='current',
                filled_data={'x': 'now'},
                html_snapshot='<p>now</p>',
                created_by=self.owner,
            )
            old_document = Document.objects.create(
                template=self.template,
                template_version=1,
                crm_entity_type='manual',
                crm_entity_id='old',
                filled_data={'x': 'old'},
                html_snapshot='<p>old</p>',
                created_by=self.owner,
            )
            Document.objects.filter(id=old_document.id).update(created_at=timezone.now() - timedelta(days=45))

        response = self.client.get('/api/tenant/plan/', **self._headers())
        self.assertEqual(response.status_code, 200)
        usage = response.json()['usage']
        self.assertEqual(usage['managers'], 3)
        self.assertEqual(usage['documents'], 1)
        self.assertEqual(usage['crm_connections'], 1)
        self.assertEqual(usage['pipelines'], 1)
