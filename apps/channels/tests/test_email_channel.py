from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

from apps.channels.models import ChatSession, MessageLog, MessengerChannel
from apps.channels.providers import normalize_incoming_payload, send_outgoing
from apps.channels.tasks import poll_email_channels, route_incoming_message
from apps.crm.models import Pipeline, Stage
from apps.users.tests.base import TenantAPITestCase

EMAIL_MSG = {
    'message_id': '<abc@mail>',
    'from_email': 'client@example.com',
    'from_name': 'Клиент',
    'subject': 'Вопрос по заказу',
    'text': 'Здравствуйте, когда отгрузка?',
}


class EmailChannelTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0, is_active=True)
        Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open', sort_order=0, auto_action={})
        self.channel = MessengerChannel.objects.create(
            name='Почта',
            channel_type='email',
            credentials={
                'imap_host': 'imap.example.com', 'username': 'sales@example.com',
                'password': 'secret', 'smtp_host': 'smtp.example.com', 'smtp_ssl': True,
            },
            auto_create_lead=False,
            is_active=True,
            status='active',
        )

    def test_normalize_email_maps_to_dialog(self):
        normalized = normalize_incoming_payload('email', EMAIL_MSG)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized['chat_id'], 'client@example.com')
        self.assertEqual(normalized['username'], 'Клиент')
        self.assertEqual(normalized['message_id'], '<abc@mail>')
        self.assertIn('Вопрос по заказу', normalized['text'])
        self.assertIn('когда отгрузка', normalized['text'])

    def test_normalize_email_without_sender_is_ignored(self):
        self.assertIsNone(normalize_incoming_payload('email', {'subject': 'x'}))

    @patch('apps.channels.tasks._broadcast_session_update')
    @patch('apps.channels.tasks._broadcast_message')
    def test_route_incoming_email_creates_message(self, _bm, _bs):
        result = route_incoming_message(self.tenant.id, self.channel.id, EMAIL_MSG)
        self.assertEqual(result['status'], 'ok')
        session = ChatSession.objects.get(channel=self.channel, external_chat_id='client@example.com')
        msg = MessageLog.objects.get(chat_session=session, direction='in')
        self.assertEqual(msg.external_message_id, '<abc@mail>')
        self.assertIn('когда отгрузка', msg.text)

    @patch('apps.channels.email_poller.fetch_new_messages', return_value=[EMAIL_MSG])
    def test_poll_dispatches_new_and_dedups(self, _fetch):
        with patch.object(route_incoming_message, 'delay') as delay:
            # Новое письмо — диспетчеризуется.
            res = poll_email_channels()
            self.assertEqual(res['dispatched'], 1)
            delay.assert_called_once()

        # Тот же Message-ID уже в логе — повторно не диспетчеризуется.
        session = ChatSession.objects.create(channel=self.channel, external_chat_id='client@example.com')
        MessageLog.objects.create(chat_session=session, direction='in', external_message_id='<abc@mail>')
        with patch.object(route_incoming_message, 'delay') as delay2:
            res2 = poll_email_channels()
            self.assertEqual(res2['dispatched'], 0)
            delay2.assert_not_called()

    def test_send_outgoing_email_success(self):
        with patch('django.core.mail.get_connection', return_value=MagicMock()), \
             patch('django.core.mail.EmailMessage.send', return_value=1):
            delivered, detail = send_outgoing(self.channel, 'client@example.com', 'Ответ из CRM')
        self.assertTrue(delivered)
        self.assertEqual(detail, '')

    def test_send_outgoing_email_smtp_error(self):
        with patch('django.core.mail.get_connection', return_value=MagicMock()), \
             patch('django.core.mail.EmailMessage.send', side_effect=smtplib.SMTPException('boom')):
            delivered, detail = send_outgoing(self.channel, 'client@example.com', 'Ответ')
        self.assertFalse(delivered)
        self.assertIn('boom', detail)

    def test_parse_email_plain(self):
        from email.message import EmailMessage as PyEmailMessage

        from apps.channels.email_poller import parse_email

        m = PyEmailMessage()
        m['From'] = 'Иван <ivan@example.com>'
        m['Subject'] = 'Привет'
        m['Message-ID'] = '<p1@mail>'
        m.set_content('Текст письма')
        parsed = parse_email(m.as_bytes())
        self.assertEqual(parsed['from_email'], 'ivan@example.com')
        self.assertEqual(parsed['from_name'], 'Иван')
        self.assertIn('Текст письма', parsed['text'])
        self.assertEqual(parsed['attachments'], [])

    def test_parse_email_html_fallback(self):
        from email.message import EmailMessage as PyEmailMessage

        from apps.channels.email_poller import parse_email

        m = PyEmailMessage()
        m['From'] = 'noreply@example.com'
        m['Subject'] = 'HTML'
        m.set_content('<html><body><p>Здравствуйте!</p><script>x()</script></body></html>', subtype='html')
        parsed = parse_email(m.as_bytes())
        self.assertIn('Здравствуйте', parsed['text'])
        self.assertNotIn('<p>', parsed['text'])
        self.assertNotIn('x()', parsed['text'])

    def test_parse_email_attachment_metadata(self):
        from email.message import EmailMessage as PyEmailMessage

        from apps.channels.email_poller import parse_email

        m = PyEmailMessage()
        m['From'] = 'client@example.com'
        m['Subject'] = 'Документ'
        m.set_content('Во вложении договор')
        m.add_attachment(b'%PDF-1.4 fake', maintype='application', subtype='pdf', filename='dogovor.pdf')
        parsed = parse_email(m.as_bytes())
        self.assertIn('договор', parsed['text'])
        self.assertEqual(len(parsed['attachments']), 1)
        self.assertEqual(parsed['attachments'][0]['filename'], 'dogovor.pdf')
        self.assertEqual(parsed['attachments'][0]['content_type'], 'application/pdf')

    def test_normalize_email_passes_attachments(self):
        payload = {**EMAIL_MSG, 'attachments': [{'filename': 'a.pdf', 'content_type': 'application/pdf'}]}
        normalized = normalize_incoming_payload('email', payload)
        self.assertEqual(normalized['attachments'], [{'filename': 'a.pdf', 'content_type': 'application/pdf'}])


class EmailParseAndThreadingTest(TenantAPITestCase):
    def _build_raw(self) -> bytes:
        from email.message import EmailMessage as PyEmail
        msg = PyEmail()
        msg['From'] = 'Клиент <client@example.com>'
        msg['Subject'] = 'Тест'
        msg['Message-ID'] = '<m1@mail>'
        msg['In-Reply-To'] = '<prev@mail>'
        msg['References'] = '<prev@mail>'
        msg.set_content('Текст письма')
        msg.add_alternative('<p>Текст <b>письма</b></p>', subtype='html')
        msg.add_attachment(b'PNGDATA', maintype='image', subtype='png', filename='pic.png')
        return msg.as_bytes()

    def test_parse_email_captures_html_threading_and_attachment_content(self):
        import base64

        from apps.channels.email_poller import parse_email
        parsed = parse_email(self._build_raw())
        self.assertEqual(parsed['in_reply_to'], '<prev@mail>')
        self.assertEqual(parsed['references'], '<prev@mail>')
        self.assertIn('<b>', parsed['html'])
        self.assertEqual(len(parsed['attachments']), 1)
        att = parsed['attachments'][0]
        self.assertEqual(att['filename'], 'pic.png')
        self.assertEqual(att['size'], len(b'PNGDATA'))
        self.assertEqual(base64.b64decode(att['content_base64']), b'PNGDATA')

    def test_send_email_sets_thread_headers(self):
        from apps.channels.providers import _send_email
        with patch('django.core.mail.EmailMessage') as MockEmail, patch('django.core.mail.get_connection'):
            MockEmail.return_value.send.return_value = 1
            ok, _ = _send_email(
                {'smtp_host': 'h', 'username': 'u', 'password': 'p', 'smtp_ssl': True},
                'to@example.com', 'Ответ', in_reply_to='<prev@mail>',
            )
        self.assertTrue(ok)
        _, kwargs = MockEmail.call_args
        self.assertEqual(kwargs['headers']['In-Reply-To'], '<prev@mail>')
        self.assertEqual(kwargs['headers']['References'], '<prev@mail>')

    def test_send_email_without_thread_id_has_no_headers(self):
        from apps.channels.providers import _send_email
        with patch('django.core.mail.EmailMessage') as MockEmail, patch('django.core.mail.get_connection'):
            MockEmail.return_value.send.return_value = 1
            _send_email({'smtp_host': 'h', 'username': 'u', 'password': 'p', 'smtp_ssl': True}, 'to@example.com', 'Ответ')
        _, kwargs = MockEmail.call_args
        self.assertIsNone(kwargs['headers'])
