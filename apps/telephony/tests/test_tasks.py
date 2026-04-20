from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.telephony.models import SIPTrunk
from apps.users.tests.base import TenantAPITestCase


class SyncFreeSwitchConfigTest(TenantAPITestCase):

    def setUp(self):
        super().setUp()

    def _make_trunk(self, name='test-gw'):
        return SIPTrunk.objects.create(
            name=name,
            trunk_type='custom_sip',
            credentials={'username': 'u', 'password': 'p', 'proxy': 'sip.example.com'},
            is_active=True,
        )

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_sync_freeswitch_config_calls_sofia_rescan(self, mock_conn_factory):
        mock_conn = MagicMock()
        mock_ev = MagicMock()
        mock_ev.data = {'Body': '+OK\n'}
        mock_conn.send.return_value = mock_ev
        mock_conn_factory.return_value = mock_conn

        trunk = self._make_trunk()
        from apps.telephony.tasks import sync_freeswitch_config
        sync_freeswitch_config(self.tenant.id, trunk.id)

        mock_conn.send.assert_called_with('api sofia rescan')

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_sync_sets_registering_status_when_rescan_ok(self, mock_conn_factory):
        mock_conn = MagicMock()
        mock_ev = MagicMock()
        mock_ev.data = {'Body': '+OK\n'}
        mock_conn.send.return_value = mock_ev
        mock_conn_factory.return_value = mock_conn

        trunk = self._make_trunk()
        from apps.telephony.tasks import sync_freeswitch_config
        sync_freeswitch_config(self.tenant.id, trunk.id)

        trunk.refresh_from_db()
        self.assertEqual(trunk.status, 'registering')
        self.assertIn('Rescan', trunk.status_detail)

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_sync_sets_error_detail_when_esl_unavailable(self, mock_conn_factory):
        mock_conn_factory.side_effect = Exception('Connection refused')

        trunk = self._make_trunk()
        from apps.telephony.tasks import sync_freeswitch_config
        sync_freeswitch_config(self.tenant.id, trunk.id)

        trunk.refresh_from_db()
        self.assertEqual(trunk.status, 'registering')
        self.assertIn('ESL', trunk.status_detail)


class TranslateRecordingPathTest(TenantAPITestCase):

    def test_translates_known_prefix(self):
        from apps.telephony.tasks import _translate_recording_path
        result = _translate_recording_path('/var/lib/freeswitch/recordings/abc.wav')
        self.assertEqual(result, 'calls/abc.wav')

    def test_returns_none_for_unknown_prefix(self):
        from apps.telephony.tasks import _translate_recording_path
        result = _translate_recording_path('/some/other/path/abc.wav')
        self.assertIsNone(result)


class ProcessFreeswithCDRRecordingTest(TenantAPITestCase):

    @patch('apps.telephony.tasks.upload_call_record_to_crm.delay')
    @patch('apps.telephony.tasks.create_lead_from_missed_call.delay')
    @patch('apps.telephony.tasks.Path')
    def test_sets_record_file_when_path_translates_and_file_exists(self, mock_path_cls, mock_lead, mock_upload):
        mock_path_instance = mock_path_cls.return_value.__truediv__.return_value
        mock_path_instance.exists.return_value = True

        import uuid as _uuid
        call_uuid = str(_uuid.uuid4())
        payload = {
            'tenant_slug': self.tenant.slug,
            'uuid': call_uuid,
            'caller_number': '+79991234567',
            'called_number': '101',
            'result': 'answered',
            'duration': 60,
            'direction': 'inbound',
            'record_file': '/var/lib/freeswitch/recordings/test.wav',
        }
        from apps.telephony.tasks import process_freeswitch_cdr
        process_freeswitch_cdr(self.tenant.id, payload)

        from apps.telephony.models import CallRecord
        record = CallRecord.objects.get(freeswitch_uuid=call_uuid)
        self.assertEqual(record.record_file, 'calls/test.wav')

    @patch('apps.telephony.tasks.upload_call_record_to_crm.delay')
    @patch('apps.telephony.tasks.create_lead_from_missed_call.delay')
    @patch('apps.telephony.tasks.Path')
    def test_skips_record_file_when_file_missing(self, mock_path_cls, mock_lead, mock_upload):
        mock_path_instance = mock_path_cls.return_value.__truediv__.return_value
        mock_path_instance.exists.return_value = False

        import uuid as _uuid
        call_uuid = str(_uuid.uuid4())
        payload = {
            'tenant_slug': self.tenant.slug,
            'uuid': call_uuid,
            'caller_number': '+79991234568',
            'called_number': '102',
            'result': 'answered',
            'duration': 30,
            'direction': 'inbound',
            'record_file': '/var/lib/freeswitch/recordings/missing.wav',
        }
        from apps.telephony.tasks import process_freeswitch_cdr
        process_freeswitch_cdr(self.tenant.id, payload)

        from apps.telephony.models import CallRecord
        record = CallRecord.objects.get(freeswitch_uuid=call_uuid)
        self.assertFalse(bool(record.record_file))


class CheckGatewayStatusTest(TenantAPITestCase):

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_returns_true_when_reged(self, mock_conn_factory):
        mock_conn = MagicMock()
        mock_ev = MagicMock()
        mock_ev.data = {'Body': 'gateway  external  sip:user@proxy  REGED  2024-01-01'}
        mock_conn.send.return_value = mock_ev
        mock_conn_factory.return_value = mock_conn

        from apps.telephony.tasks import _check_gateway_status
        is_reg, detail = _check_gateway_status('my-gw')
        self.assertTrue(is_reg)
        self.assertIn('Зарегистрирован', detail)

    @patch('apps.telephony.tasks._get_esl_connection')
    def test_returns_false_when_noreg(self, mock_conn_factory):
        mock_conn = MagicMock()
        mock_ev = MagicMock()
        mock_ev.data = {'Body': 'NOREG'}
        mock_conn.send.return_value = mock_ev
        mock_conn_factory.return_value = mock_conn

        from apps.telephony.tasks import _check_gateway_status
        is_reg, detail = _check_gateway_status('my-gw')
        self.assertFalse(is_reg)
