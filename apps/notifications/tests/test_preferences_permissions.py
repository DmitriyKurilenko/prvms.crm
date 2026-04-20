from __future__ import annotations

import json
from unittest.mock import patch

from apps.notifications.models import NotificationPreference
from apps.users.tests.base import TenantAPITestCase


class NotificationPreferencesPermissionsTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='notif_owner@example.com', username='notif_owner')
        self.manager = self.create_user(role='manager', email='notif_manager@example.com', username='notif_manager')

    def test_manager_cannot_list_preferences(self):
        response = self.client.get(
            '/api/notifications/preferences/',
            **self.auth_headers(self.manager, host='localhost'),
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_preferences(self):
        payload = [
            {
                'event': 'new_deal_created',
                'channel': 'in_app',
                'is_enabled': True,
                'recipient_roles': ['owner', 'admin'],
            }
        ]
        response = self.client.put(
            '/api/notifications/preferences/',
            data=json.dumps(payload),
            content_type='application/json',
            **self.auth_headers(self.owner, host='localhost'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NotificationPreference.objects.filter(
                event='new_deal_created',
                channel='in_app',
                is_enabled=True,
            ).exists()
        )

    @patch('apps.notifications.api.notify')
    def test_owner_can_send_test_notification(self, mock_notify):
        response = self.client.post(
            '/api/notifications/test/',
            content_type='application/json',
            **self.auth_headers(self.owner, host='localhost'),
        )
        self.assertEqual(response.status_code, 200)
        mock_notify.assert_called_once()
