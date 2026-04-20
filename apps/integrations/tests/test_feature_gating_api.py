from __future__ import annotations

import json

from django_tenants.utils import schema_context, tenant_context

from apps.billing.models import Feature
from apps.integrations.models import CRMConnection, WebhookEndpoint
from apps.tenants.models import Tenant
from apps.users.tests.base import TenantAPITestCase


class IntegrationsFeatureGatingAPITest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(
            role='owner',
            email='integration_gate_owner@example.com',
            username='integration_gate_owner',
        )

    def _headers(self):
        return self.auth_headers(self.owner, host='localhost')

    def _disable_feature(self, feature_code: str):
        with schema_context('public'):
            tenant = Tenant.objects.select_related('plan').get(id=self.tenant.id)
            feature = Feature.objects.get(code=feature_code)
            tenant.plan.features.remove(feature)

    def _api(self, method: str, path: str, payload: dict | None = None):
        kwargs = dict(self._headers())
        if payload is not None:
            kwargs['data'] = json.dumps(payload)
            kwargs['content_type'] = 'application/json'
        return getattr(self.client, method)(path, **kwargs)

    def test_connection_operations_are_blocked_when_amocrm_feature_is_disabled(self):
        with tenant_context(self.tenant):
            connection = CRMConnection.objects.create(
                crm_type='amocrm',
                name='amo gated',
                credentials={'access_token': 'token'},
                integration_mode='webhook',
            )
            webhook = WebhookEndpoint.objects.create(
                crm_connection=connection,
                event_type='default',
                secret_token='secret',
                is_active=True,
            )

        self._disable_feature('crm_amocrm')

        list_response = self._api('get', '/api/integrations/connections/')
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(row['id'] == connection.id for row in list_response.json()))

        cases = [
            ('patch', f'/api/integrations/connections/{connection.id}/', {'name': 'new-name'}),
            ('post', f'/api/integrations/connections/{connection.id}/sync-users/', {}),
            ('post', f'/api/integrations/connections/{connection.id}/health-check/', {}),
            ('post', f'/api/integrations/connections/{connection.id}/test/', {}),
            ('post', f'/api/integrations/connections/{connection.id}/reconnect/', {}),
            ('get', f'/api/integrations/connections/{connection.id}/errors/', None),
            ('get', f'/api/integrations/connections/{connection.id}/managers/', None),
            ('get', f'/api/integrations/connections/{connection.id}/webhooks/', None),
            (
                'post',
                f'/api/integrations/connections/{connection.id}/webhooks/',
                {'event_type': 'lead.created', 'is_active': True},
            ),
            (
                'post',
                f'/api/integrations/connections/{connection.id}/webhooks/{webhook.id}/rotate-secret/',
                {},
            ),
            ('delete', f'/api/integrations/connections/{connection.id}/', None),
        ]

        for method, path, payload in cases:
            response = self._api(method, path, payload)
            self.assertEqual(response.status_code, 403, msg=f'{method.upper()} {path} -> {response.status_code}')

    def test_connection_operations_are_blocked_when_bitrix_feature_is_disabled(self):
        with tenant_context(self.tenant):
            connection = CRMConnection.objects.create(
                crm_type='bitrix24',
                name='bitrix gated',
                credentials={'webhook_url': 'https://example.bitrix24.ru/rest/1/abc/'},
                integration_mode='webhook',
            )

        self._disable_feature('crm_bitrix24')
        response = self._api('post', f'/api/integrations/connections/{connection.id}/test/', {})
        self.assertEqual(response.status_code, 403)
