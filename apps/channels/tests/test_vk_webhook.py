from __future__ import annotations

import json
from unittest.mock import patch

from apps.channels.models import MessengerChannel
from apps.users.tests.base import TenantAPITestCase


class VkWebhookTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.vk_channel = MessengerChannel.objects.create(
            name='VK Group',
            channel_type='vk',
            credentials={'confirmation_code': 'vkconfirm123', 'secret_key': 'supersecret'},
            status='active',
            is_active=True,
        )

    def test_confirmation_returns_code(self):
        payload = {'type': 'confirmation', 'group_id': 222}
        resp = self.client.post(
            f'/channels/webhook/{self.tenant.slug}/vk/{self.vk_channel.id}/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'vkconfirm123')
        self.assertEqual(resp['Content-Type'], 'text/plain')

    @patch('apps.channels.public_views.route_incoming_message.delay')
    def test_message_new_with_correct_secret(self, mock_delay):
        payload = {
            'type': 'message_new',
            'object': {
                'message': {'peer_id': 111, 'text': 'hi', 'id': 1, 'attachments': []}
            },
            'group_id': 222,
            'secret': 'supersecret',
        }
        resp = self.client.post(
            f'/channels/webhook/{self.tenant.slug}/vk/{self.vk_channel.id}/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_called_once()
        self.assertEqual(resp.json()['detail'], 'ok')

    def test_wrong_secret_returns_403(self):
        payload = {
            'type': 'message_new',
            'object': {
                'message': {'peer_id': 111, 'text': 'hi', 'id': 1}
            },
            'group_id': 222,
            'secret': 'wrong',
        }
        resp = self.client.post(
            f'/channels/webhook/{self.tenant.slug}/vk/{self.vk_channel.id}/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_missing_channel_returns_404(self):
        payload = {'type': 'confirmation', 'group_id': 222}
        resp = self.client.post(
            f'/channels/webhook/{self.tenant.slug}/vk/99999/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)
