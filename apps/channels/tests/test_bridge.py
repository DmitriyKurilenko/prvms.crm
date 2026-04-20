from __future__ import annotations

from unittest.mock import patch

from apps.channels.models import ChatSession, MessageLog, MessengerChannel
from apps.channels.providers import normalize_incoming_payload
from apps.channels.tasks import route_incoming_message, route_outgoing_message
from apps.crm.models import Deal, Pipeline, Stage
from apps.users.tests.base import TenantAPITestCase


class ChannelsBridgeTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0, is_active=True)
        Stage.objects.create(
            pipeline=self.pipeline,
            name='New',
            stage_type='open',
            sort_order=0,
            auto_action={},
        )
        self.channel = MessengerChannel.objects.create(
            name='Telegram',
            channel_type='telegram',
            credentials={},
            auto_create_lead=True,
            is_active=True,
            status='active',
        )

    def test_normalize_incoming_payload_for_telegram_and_whatsapp(self):
        telegram_payload = {
            'message': {
                'message_id': 11,
                'text': 'hello',
                'chat': {'id': 777},
                'from': {'username': 'john'},
            }
        }
        telegram = normalize_incoming_payload('telegram', telegram_payload)
        self.assertEqual(telegram['chat_id'], '777')
        self.assertEqual(telegram['username'], 'john')
        self.assertEqual(telegram['text'], 'hello')

        wa_payload = {'from': '+79990000000', 'name': 'Client', 'body': 'hey'}
        whatsapp = normalize_incoming_payload('whatsapp', wa_payload)
        self.assertEqual(whatsapp['phone'], '+79990000000')
        self.assertEqual(whatsapp['text'], 'hey')

    def test_route_incoming_message_creates_session_message_and_deal_for_builtin_crm(self):
        payload = {
            'message': {
                'message_id': 12,
                'text': 'Need help',
                'chat': {'id': 12345},
                'from': {'username': 'alice'},
            },
            'phone': '+79990001122',
        }
        result = route_incoming_message(self.tenant.id, self.channel.id, payload)
        self.assertEqual(result['status'], 'ok')

        session = ChatSession.objects.get(channel=self.channel, external_chat_id='12345')
        message = MessageLog.objects.get(chat_session=session)
        self.assertEqual(message.direction, 'in')
        self.assertEqual(message.text, 'Need help')
        self.assertTrue(session.crm_lead_id)
        self.assertEqual(Deal.objects.count(), 1)

    @patch('apps.channels.tasks.send_outgoing', return_value=(False, 'provider error'))
    def test_route_outgoing_message_logs_delivery_error(self, _mock_send):
        session = ChatSession.objects.create(
            channel=self.channel,
            external_chat_id='2000',
            external_user_name='Client',
            is_active=True,
        )
        result = route_outgoing_message(
            self.tenant.id,
            self.channel.id,
            session.id,
            {'text': 'Hello', 'attachments': []},
        )
        self.assertEqual(result['status'], 'error')

        message = MessageLog.objects.filter(chat_session=session, direction='out').latest('id')
        self.assertFalse(message.delivered)
        self.assertIn('provider error', message.error)
