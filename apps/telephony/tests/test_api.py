from __future__ import annotations

import json
from unittest.mock import patch

from apps.telephony.models import SIPTrunk
from apps.users.tests.base import TenantAPITestCase


class TestTrunkAPITest(TenantAPITestCase):

    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='trunk_test_owner@example.com', username='trunk_test_owner')

    def _make_trunk(self, name='api-gw'):
        return SIPTrunk.objects.create(
            name=name,
            trunk_type='custom_sip',
            credentials={'username': 'u', 'password': 'p', 'proxy': 'sip.example.com'},
            is_active=True,
        )

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_test_trunk_returns_502_when_esl_unavailable(self, mock_conn_factory):
        mock_conn_factory.side_effect = Exception('ESL down')
        trunk = self._make_trunk()
        headers = self.auth_headers(self.owner)
        response = self.client.post(f'/api/telephony/trunks/{trunk.id}/test/', **headers)
        self.assertEqual(response.status_code, 502)

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_test_trunk_sets_active_when_reged(self, mock_conn_factory):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_ev = MagicMock()
        mock_ev.data = {'Body': 'REGED'}
        mock_conn.send.return_value = mock_ev
        mock_conn_factory.return_value = mock_conn

        trunk = self._make_trunk()
        headers = self.auth_headers(self.owner)
        response = self.client.post(f'/api/telephony/trunks/{trunk.id}/test/', **headers)
        self.assertEqual(response.status_code, 200)
        trunk.refresh_from_db()
        self.assertEqual(trunk.status, 'active')

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_test_trunk_sets_error_when_noreg(self, mock_conn_factory):
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_ev = MagicMock()
        mock_ev.data = {'Body': 'NOREG'}
        mock_conn.send.return_value = mock_ev
        mock_conn_factory.return_value = mock_conn

        trunk = self._make_trunk()
        headers = self.auth_headers(self.owner)
        response = self.client.post(f'/api/telephony/trunks/{trunk.id}/test/', **headers)
        self.assertEqual(response.status_code, 200)
        trunk.refresh_from_db()
        self.assertEqual(trunk.status, 'error')


class ExolveTrunkTest(TenantAPITestCase):

    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='exolve_owner@example.com', username='exolve_owner')

    @patch('apps.telephony.tasks.sync_freeswitch_config.delay')
    def test_create_exolve_trunk_sets_default_proxy(self, _mock_delay):
        headers = self.auth_headers(self.owner)
        response = self.client.post(
            '/api/telephony/trunks/',
            data=json.dumps({
                'name': 'exolve-gw',
                'trunk_type': 'exolve',
                'credentials': {'username': '12345678', 'password': 'secret'},
            }),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        trunk = SIPTrunk.objects.get(name='exolve-gw')
        self.assertEqual(trunk.credentials.get('proxy'), 'sip.exolve.ru')

    @patch('apps.telephony.tasks.sync_freeswitch_config.delay')
    def test_create_exolve_trunk_respects_explicit_proxy(self, _mock_delay):
        headers = self.auth_headers(self.owner)
        response = self.client.post(
            '/api/telephony/trunks/',
            data=json.dumps({
                'name': 'exolve-custom',
                'trunk_type': 'exolve',
                'credentials': {'username': '99', 'password': 'pw', 'proxy': 'custom.exolve.ru'},
            }),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        trunk = SIPTrunk.objects.get(name='exolve-custom')
        self.assertEqual(trunk.credentials.get('proxy'), 'custom.exolve.ru')
