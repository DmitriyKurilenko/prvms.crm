from __future__ import annotations

import json
from datetime import timedelta

from django.utils import timezone
from django_tenants.utils import schema_context

from apps.contracts.models import Contract, ContractTemplate
from apps.users.tests.base import TenantAPITestCase


class ContractLimitTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='limits_owner@example.com', username='limits_owner')
        self.template = ContractTemplate.objects.create(
            name='Limit Template',
            version=1,
            html_body='<h1>{{ x }}</h1>',
            variable_schema=[{'key': 'x', 'sample': '1'}],
            is_active=True,
        )

    def test_generate_contract_uses_monthly_limit(self):
        with schema_context('public'):
            tenant = self.tenant.__class__.objects.get(id=self.tenant.id)
            plan = tenant.plan
            plan.max_contracts_per_month = 1
            plan.save(update_fields=['max_contracts_per_month'])

        Contract.objects.create(
            template=self.template,
            template_version=1,
            crm_entity_type='manual',
            crm_entity_id='existing',
            filled_data={'x': 'existing'},
            html_snapshot='<h1>existing</h1>',
            created_by=self.owner,
            created_at=timezone.now() - timedelta(days=1),
        )

        headers = self.auth_headers(self.owner, host='localhost')
        response = self.client.post(
            '/api/contracts/generate',
            data=json.dumps(
                {
                    'template_id': self.template.id,
                    'filled_data': {'x': 'new'},
                    'signing_method': 'email_otp',
                }
            ),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('limit', response.json()['detail'].lower())
