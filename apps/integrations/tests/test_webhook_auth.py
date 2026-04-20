from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

from apps.integrations.models import CRMConnection, WebhookEndpoint
from apps.users.tests.base import TenantAPITestCase


class IntegrationsWebhookAuthTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.connection = CRMConnection.objects.create(
            crm_type='amocrm',
            name='amo',
            credentials={},
            is_active=True,
        )
        self.endpoint = WebhookEndpoint.objects.create(
            crm_connection=self.connection,
            event_type='default',
            secret_token='secret-123',
            is_active=True,
        )

    def _webhook_url(self):
        return f'/wh/{self.tenant.slug}/{self.endpoint.uuid}/'

    def test_rejects_invalid_webhook_token(self):
        response = self.client.post(
            self._webhook_url(),
            data=json.dumps({'trigger': 'new_lead'}),
            content_type='application/json',
            HTTP_HOST='localhost',
            HTTP_X_WEBHOOK_TOKEN='wrong',
        )
        self.assertEqual(response.status_code, 403)

    def test_amocrm_requires_signature_when_secret_is_configured(self):
        self.connection.credentials = {'webhook_hmac_secret': 'hmac-key'}
        self.connection.save(update_fields=['credentials'])
        response = self.client.post(
            self._webhook_url(),
            data=json.dumps({'trigger': 'new_lead'}),
            content_type='application/json',
            HTTP_HOST='localhost',
            HTTP_X_WEBHOOK_TOKEN='secret-123',
        )
        self.assertEqual(response.status_code, 403)

    @patch('apps.integrations.webhook_views.process_incoming_webhook.delay')
    def test_amocrm_accepts_valid_signature_and_queues_task(self, mock_delay):
        self.connection.credentials = {'webhook_hmac_secret': 'hmac-key'}
        self.connection.save(update_fields=['credentials'])
        payload = {
            'trigger': 'new_lead',
            'entity_type': 'lead',
            'entity_id': '42',
        }
        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(b'hmac-key', body, hashlib.sha256).hexdigest()

        response = self.client.post(
            self._webhook_url(),
            data=body,
            content_type='application/json',
            HTTP_HOST='localhost',
            HTTP_X_WEBHOOK_TOKEN='secret-123',
            HTTP_X_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once()
        args, _kwargs = mock_delay.call_args
        self.assertEqual(args[0], self.tenant.id)
        self.assertEqual(args[1], 'new_lead')

    def test_bitrix_rejects_invalid_application_token(self):
        self.connection.crm_type = 'bitrix24'
        self.connection.credentials = {'application_token': 'app-token'}
        self.connection.save(update_fields=['crm_type', 'credentials'])

        response = self.client.post(
            self._webhook_url(),
            data=json.dumps({'trigger': 'new_lead', 'application_token': 'wrong'}),
            content_type='application/json',
            HTTP_HOST='localhost',
            HTTP_X_WEBHOOK_TOKEN='secret-123',
        )
        self.assertEqual(response.status_code, 403)

    @patch('apps.integrations.webhook_views.route_outgoing_message.delay')
    def test_outgoing_message_trigger_routes_to_channels_task(self, mock_route_delay):
        payload = {
            'trigger': 'outgoing_message',
            'channel_id': 11,
            'chat_session_id': 22,
            'text': 'hello',
        }
        response = self.client.post(
            self._webhook_url(),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_HOST='localhost',
            HTTP_X_WEBHOOK_TOKEN='secret-123',
        )
        self.assertEqual(response.status_code, 200)
        mock_route_delay.assert_called_once_with(self.tenant.id, 11, 22, payload)
