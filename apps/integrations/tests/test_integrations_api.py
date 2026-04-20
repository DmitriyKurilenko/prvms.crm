from __future__ import annotations

import json
from unittest.mock import patch

from django.test import override_settings
from django_tenants.utils import tenant_context

from apps.integrations.models import CRMConnection, IntegrationErrorLog, WebhookEndpoint
from apps.users.tests.base import TenantAPITestCase


@override_settings(
    AMOCRM_CLIENT_ID='amo_client',
    AMOCRM_CLIENT_SECRET='amo_secret',
    AMOCRM_REDIRECT_URI='http://localhost:18100/api/integrations/oauth/amocrm/callback/',
    BITRIX24_APP_ID='bx_app',
    BITRIX24_APP_SECRET='bx_secret',
)
class IntegrationsAPITest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='integrations_owner@example.com', username='integrations_owner')
        self.owner.set_password('OwnerPass123')
        self.owner.save(update_fields=['password'])

    def _headers(self):
        return self.auth_headers(self.owner, host='localhost')

    def test_marketplace_start_creates_tenant_bound_connection(self):
        response = self.client.post(
            '/api/integrations/marketplace/amocrm/install/',
            data=json.dumps({'name': 'amo marketplace'}),
            content_type='application/json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['crm_type'], 'amocrm')
        self.assertEqual(payload['install_mode'], 'marketplace')
        self.assertIn('authorize_url', payload)

        with tenant_context(self.tenant):
            connection = CRMConnection.objects.get(id=payload['connection_id'])
            self.assertEqual(connection.integration_mode, 'marketplace')
            self.assertEqual(connection.crm_type, 'amocrm')
            self.assertTrue(WebhookEndpoint.objects.filter(crm_connection=connection, event_type='default').exists())

    @patch('apps.integrations.api.check_crm_connections_health.delay')
    @patch('apps.integrations.api.sync_crm_users.delay')
    @patch('apps.integrations.webhook_views.process_incoming_webhook.delay')
    def test_marketplace_callback_autoconfig_and_webhook_flow(
        self,
        mock_webhook_delay,
        mock_sync_delay,
        mock_health_delay,
    ):
        start = self.client.post(
            '/api/integrations/marketplace/amocrm/install/',
            data=json.dumps({'name': 'amo app'}),
            content_type='application/json',
            **self._headers(),
        )
        self.assertEqual(start.status_code, 200)
        start_payload = start.json()
        connection_id = start_payload['connection_id']

        callback = self.client.get(
            '/api/integrations/oauth/amocrm/callback/',
            {
                'state': start_payload['state'],
                'code': 'oauth-code-123',
                'access_token': 'oauth-token-123',
                'scope': 'crm users',
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(callback.status_code, 200)
        callback_payload = callback.json()
        self.assertEqual(callback_payload['connection_id'], connection_id)
        self.assertEqual(callback_payload['status_code'], 'requires_authorization')

        with tenant_context(self.tenant):
            connection = CRMConnection.objects.get(id=connection_id)
            endpoint = WebhookEndpoint.objects.get(crm_connection=connection, event_type='default')
            self.assertEqual(connection.integration_mode, 'marketplace')
            self.assertEqual(connection.credentials.get('access_token'), 'oauth-token-123')
        mock_sync_delay.assert_called_once_with(self.tenant.id, connection_id)
        mock_health_delay.assert_called_once()

        webhook_response = self.client.post(
            f'/wh/{self.tenant.slug}/{endpoint.uuid}/',
            data=json.dumps({'trigger': 'new_lead', 'entity_type': 'lead', 'entity_id': '42'}),
            content_type='application/json',
            HTTP_HOST='localhost',
            HTTP_X_WEBHOOK_TOKEN=endpoint.secret_token,
        )
        self.assertEqual(webhook_response.status_code, 200)
        mock_webhook_delay.assert_called_once()

        with tenant_context(self.tenant):
            endpoint.refresh_from_db()
            connection.refresh_from_db()
            self.assertIsNotNone(endpoint.last_received_at)
            self.assertIsNotNone(connection.last_webhook_at)

    def test_test_endpoint_reports_insufficient_scope_and_error_log(self):
        create = self.client.post(
            '/api/integrations/connections/',
            data=json.dumps(
                {
                    'crm_type': 'amocrm',
                    'name': 'amo limited scopes',
                    'integration_mode': 'marketplace',
                    'credentials': {
                        'base_url': 'https://example.amocrm.ru',
                        'access_token': 'token-1',
                        'scope': 'crm',
                        'mock_users': [{'id': 1, 'name': 'Manager One', 'email': 'manager.one@example.com'}],
                    },
                }
            ),
            content_type='application/json',
            **self._headers(),
        )
        self.assertEqual(create.status_code, 200)
        connection_id = create.json()['id']

        test_response = self.client.post(
            f'/api/integrations/connections/{connection_id}/test/',
            data=json.dumps({}),
            content_type='application/json',
            **self._headers(),
        )
        self.assertEqual(test_response.status_code, 200)
        payload = test_response.json()
        self.assertEqual(payload['status_code'], 'insufficient_scope')

        errors = self.client.get(
            f'/api/integrations/connections/{connection_id}/errors/',
            **self._headers(),
        )
        self.assertEqual(errors.status_code, 200)
        entries = errors.json()
        self.assertTrue(any(item['code'] == 'scope_missing' for item in entries))
        self.assertTrue(IntegrationErrorLog.objects.filter(crm_connection_id=connection_id, code='scope_missing').exists())
