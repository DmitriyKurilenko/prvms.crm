from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.channels.providers import (
    get_vk_group_info,
    normalize_incoming_payload,
    register_vk_callback,
    send_outgoing,
    unregister_vk_callback,
)
from apps.users.tests.base import TenantAPITestCase


class VkProviderTest(TenantAPITestCase):
    def test_normalize_message_new(self):
        payload = {
            'type': 'message_new',
            'object': {
                'message': {
                    'from_id': 12345,
                    'peer_id': 12345,
                    'text': 'Привет',
                    'id': 67890,
                    'date': 1234567890,
                    'attachments': [],
                },
                'client_info': {},
            },
            'group_id': 222222222,
            'secret': 'abc',
        }
        result = normalize_incoming_payload('vk', payload)
        self.assertIsNotNone(result)
        self.assertEqual(result['chat_id'], '12345')
        self.assertEqual(result['username'], '')
        self.assertEqual(result['phone'], '')
        self.assertEqual(result['text'], 'Привет')
        self.assertEqual(result['message_id'], '67890')
        self.assertEqual(result['attachments'], [])

    def test_normalize_ignores_confirmation(self):
        payload = {'type': 'confirmation', 'group_id': 222222222}
        result = normalize_incoming_payload('vk', payload)
        self.assertIsNone(result)

    def test_normalize_ignores_wall_reply(self):
        payload = {'type': 'wall_reply_new', 'object': {'wall_reply': {}}}
        result = normalize_incoming_payload('vk', payload)
        self.assertIsNone(result)

    def test_normalize_handles_attachments(self):
        payload = {
            'type': 'message_new',
            'object': {
                'message': {
                    'peer_id': 111,
                    'text': 'Photo',
                    'id': 1,
                    'attachments': [{'type': 'photo', 'photo': {'id': 1}}],
                }
            }
        }
        result = normalize_incoming_payload('vk', payload)
        self.assertEqual(result['attachments'], [{'type': 'photo', 'photo': {'id': 1}}])

    @patch('apps.channels.providers.requests.post')
    def test_send_outgoing_success(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {'response': 42})
        from apps.channels.models import MessengerChannel
        channel = MessengerChannel(
            channel_type='vk',
            credentials={'access_token': 'tok'},
        )
        ok, msg_id = send_outgoing(channel, '12345', 'Hello')
        self.assertTrue(ok)
        self.assertEqual(msg_id, '42')
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['data']['peer_id'], '12345')
        self.assertEqual(kwargs['data']['message'], 'Hello')
        self.assertIn('random_id', kwargs['data'])
        self.assertEqual(kwargs['data']['access_token'], 'tok')
        self.assertEqual(kwargs['data']['v'], '5.199')

    @patch('apps.channels.providers.requests.post')
    def test_send_outgoing_error(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {'error': {'error_msg': 'Access denied'}})
        from apps.channels.models import MessengerChannel
        channel = MessengerChannel(
            channel_type='vk',
            credentials={'access_token': 'bad'},
        )
        ok, error = send_outgoing(channel, '12345', 'Hello')
        self.assertFalse(ok)
        self.assertEqual(error, 'Access denied')

    @patch('apps.channels.providers.requests.get')
    def test_register_vk_callback_full_flow(self, mock_get):
        mock_get.side_effect = [
            MagicMock(json=lambda: {'response': {'code': 'conf123'}}),
            MagicMock(json=lambda: {'response': {'server_id': 7}}),
            MagicMock(json=lambda: {'response': 1}),
        ]
        from apps.channels.models import MessengerChannel
        channel = MessengerChannel.objects.create(
            channel_type='vk',
            name='Test',
            credentials={'group_id': 222, 'access_token': 'tok'},
        )
        ok, detail = register_vk_callback(channel, 'https://example.com', 'tenant1')
        self.assertTrue(ok)
        self.assertEqual(detail, 'ok')
        channel.refresh_from_db()
        creds = channel.credentials
        self.assertEqual(creds['confirmation_code'], 'conf123')
        self.assertTrue(creds['secret_key'])
        self.assertEqual(creds['server_id'], 7)

    @patch('apps.channels.providers.requests.get')
    def test_unregister_vk_callback(self, mock_get):
        mock_get.return_value = MagicMock(json=lambda: {'response': 1})
        from apps.channels.models import MessengerChannel
        channel = MessengerChannel(
            channel_type='vk',
            credentials={'group_id': 222, 'access_token': 'tok', 'server_id': 7},
        )
        ok, detail = unregister_vk_callback(channel)
        self.assertTrue(ok)

    @patch('apps.channels.providers.requests.get')
    def test_get_vk_group_info(self, mock_get):
        mock_get.return_value = MagicMock(
            json=lambda: {'response': [{'name': 'Test Group', 'photo_200': 'http://pic.jpg'}]}
        )
        result = get_vk_group_info('tok', 222)
        self.assertEqual(result['name'], 'Test Group')
        self.assertEqual(result['photo_200'], 'http://pic.jpg')

    @patch('apps.channels.providers.requests.get')
    def test_get_vk_group_info_error(self, mock_get):
        mock_get.return_value = MagicMock(
            json=lambda: {'error': {'error_msg': 'Access denied'}}
        )
        result = get_vk_group_info('bad', 222)
        self.assertEqual(result['error'], 'Access denied')
