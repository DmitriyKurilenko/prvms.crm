from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.core import signing

from apps.channels.models import MessengerChannel
from apps.users.tests.base import TenantAPITestCase


class VkOAuthAPITest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(role='admin')
        self.headers = self.auth_headers(self.user)

    def test_start_returns_authorize_url(self):
        with self.settings(VK_APP_ID='12345'):
            resp = self.client.post('/api/channels/oauth/vk/start/', **self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('oauth.vk.com/authorize', data['authorize_url'])
        self.assertIn('client_id=12345', data['authorize_url'])
        self.assertTrue(data['state'])
        # Verify state is valid
        state = signing.loads(data['state'], salt='vk-channel-oauth', max_age=3600)
        self.assertEqual(state['tenant_id'], self.tenant.id)
        self.assertEqual(state['user_id'], self.user.id)

    def test_start_requires_admin(self):
        viewer = self.create_user(role='viewer')
        viewer_headers = self.auth_headers(viewer)
        with self.settings(VK_APP_ID='12345'):
            resp = self.client.post('/api/channels/oauth/vk/start/', **viewer_headers)
        self.assertEqual(resp.status_code, 403)

    @patch('apps.channels.oauth_api.get_vk_group_info')
    @patch('apps.channels.oauth_api.register_vk_callback')
    def test_complete_creates_channels(self, mock_register, mock_info):
        mock_info.return_value = {'name': 'Test Group'}
        mock_register.return_value = (True, 'ok')
        with self.settings(VK_APP_ID='12345', WEBHOOK_BASE_URL='https://example.com'):
            state = signing.dumps(
                {'tenant_id': self.tenant.id, 'user_id': self.user.id, 'nonce': 'n1'},
                salt='vk-channel-oauth',
            )
            resp = self.client.post(
                '/api/channels/oauth/vk/complete/',
                data={'state': state, 'tokens': [{'group_id': 222, 'access_token': 'tok'}]},
                content_type='application/json',
                **self.headers,
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['created']), 1)
        self.assertEqual(data['created'][0]['group_id'], 222)
        self.assertEqual(data['created'][0]['name'], 'Test Group')
        self.assertEqual(len(data['failed']), 0)
        channel = MessengerChannel.objects.get(channel_type='vk')
        self.assertEqual(channel.credentials['group_id'], 222)
        self.assertEqual(channel.credentials['access_token'], 'tok')

    def test_complete_invalid_state_returns_400(self):
        with self.settings(VK_APP_ID='12345', WEBHOOK_BASE_URL='https://example.com'):
            resp = self.client.post(
                '/api/channels/oauth/vk/complete/',
                data={'state': 'badstate', 'tokens': [{'group_id': 222, 'access_token': 'tok'}]},
                content_type='application/json',
                **self.headers,
            )
        self.assertEqual(resp.status_code, 400)

    def test_complete_state_from_other_tenant_rejected(self):
        other_state = signing.dumps(
            {'tenant_id': 99999, 'user_id': self.user.id, 'nonce': 'n1'},
            salt='vk-channel-oauth',
        )
        with self.settings(VK_APP_ID='12345', WEBHOOK_BASE_URL='https://example.com'):
            resp = self.client.post(
                '/api/channels/oauth/vk/complete/',
                data={'state': other_state, 'tokens': [{'group_id': 222, 'access_token': 'tok'}]},
                content_type='application/json',
                **self.headers,
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tenant mismatch', resp.json()['detail'])

    @patch('apps.channels.oauth_api.get_vk_group_info')
    @patch('apps.channels.oauth_api.register_vk_callback')
    def test_complete_partial_failure(self, mock_register, mock_info):
        def side_effect(access_token, group_id):
            if group_id == 222:
                return {'name': 'Good'}
            return {'error': 'Access denied'}
        mock_info.side_effect = side_effect
        mock_register.return_value = (True, 'ok')
        with self.settings(VK_APP_ID='12345', WEBHOOK_BASE_URL='https://example.com'):
            state = signing.dumps(
                {'tenant_id': self.tenant.id, 'user_id': self.user.id, 'nonce': 'n1'},
                salt='vk-channel-oauth',
            )
            resp = self.client.post(
                '/api/channels/oauth/vk/complete/',
                data={'state': state, 'tokens': [
                    {'group_id': 222, 'access_token': 'tok1'},
                    {'group_id': 333, 'access_token': 'tok2'},
                ]},
                content_type='application/json',
                **self.headers,
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['created']), 1)
        self.assertEqual(data['created'][0]['group_id'], 222)
        self.assertEqual(len(data['failed']), 1)
        self.assertEqual(data['failed'][0]['group_id'], 333)
