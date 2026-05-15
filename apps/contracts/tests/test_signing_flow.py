from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from django_tenants.utils import schema_context

from apps.contracts.models import Contract, ContractTemplate, SigningSession
from apps.contracts.services import SigningError, send_for_signing, request_signing_otp, verify_signing
from apps.tenants.models import SigningTokenLookup
from apps.users.tests.base import TenantAPITestCase


class ContractSigningFlowTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='contracts_owner@example.com', username='contracts_owner')
        self.template = ContractTemplate.objects.create(
            name='Test Template',
            version=1,
            html_body='<h1>{{ deal_name }}</h1>',
            variable_schema=[{'key': 'deal_name', 'sample': 'Deal'}],
            is_active=True,
        )
        self.contract = Contract.objects.create(
            template=self.template,
            template_version=self.template.version,
            crm_entity_type='manual',
            crm_entity_id='entity-1',
            filled_data={'deal_name': 'Deal A'},
            html_snapshot='<h1>Deal A</h1>',
            status='draft',
            signing_method='email_otp',
            created_by=self.owner,
        )

    @patch('apps.contracts.signing._send_otp')
    def test_send_for_signing_creates_session(self, _mock_send_otp):
        session = send_for_signing(self.contract, 'client@example.com')
        self.assertIsNotNone(session.token)
        self.assertEqual(session.otp_sent_to, 'client@example.com')
        self.assertEqual(session.otp_code_hash, '')  # no OTP yet
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, 'sent')

    @patch('apps.contracts.signing._send_otp')
    def test_request_otp_sends_code(self, _mock_send_otp):
        session = send_for_signing(self.contract, 'client@example.com')
        test_otp = request_signing_otp(str(session.token))
        self.assertIsNotNone(test_otp)
        session.refresh_from_db()
        self.assertNotEqual(session.otp_code_hash, '')

    @patch('apps.contracts.signing._send_otp')
    def test_verify_invalid_otp_increments_attempts(self, _mock_send_otp):
        session = send_for_signing(self.contract, 'client@example.com')
        request_signing_otp(str(session.token))

        with self.assertRaises(SigningError):
            verify_signing(str(session.token), '000000', ip_address='127.0.0.1', user_agent='test-agent')

        session.refresh_from_db()
        self.assertEqual(session.attempts, 1)
        self.assertIsNone(session.verified_at)

    @patch('apps.contracts.tasks.notify_contract_signed.delay')
    @patch('apps.contracts.signing._send_otp')
    @patch('apps.contracts.signing._generate_otp', return_value='123456')
    def test_verify_success_signs_contract_and_marks_lookup_used(self, _mock_generate, _mock_send_otp, mock_notify):
        session = send_for_signing(self.contract, 'client@example.com')
        request_signing_otp(str(session.token))

        signed = verify_signing(str(session.token), '123456', ip_address='127.0.0.1', user_agent='test-agent')
        self.assertEqual(signed.status, 'signed')
        self.assertIsNotNone(signed.signed_at)

        # Verify cryptographic signature record
        signed.refresh_from_db()
        self.assertIsNotNone(signed.signature_data)
        self.assertEqual(signed.signature_data['type'], 'simple_electronic_signature')
        self.assertEqual(signed.signature_data['algorithm'], 'HMAC-SHA256')
        self.assertIn('signature', signed.signature_data)

        with schema_context('public'):
            lookup = SigningTokenLookup.objects.get(token=session.token)
            self.assertEqual(lookup.tenant_id, self.tenant.id)
            self.assertIsNotNone(lookup.used_at)

        mock_notify.assert_called_once_with(self.tenant.id, self.contract.id)

    @patch('apps.contracts.signing._send_otp')
    @patch('apps.contracts.signing._generate_otp', return_value='111111')
    def test_verify_marks_contract_expired_when_otp_expired(self, _mock_generate, _mock_send_otp):
        session = send_for_signing(self.contract, 'client@example.com')
        request_signing_otp(str(session.token))
        SigningSession.objects.filter(id=session.id).update(
            otp_expires_at=timezone.now() - timedelta(minutes=1)
        )

        with self.assertRaises(SigningError):
            verify_signing(str(session.token), '111111', ip_address='127.0.0.1', user_agent='test-agent')

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, 'expired')
