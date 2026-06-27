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

    # ---------- normalize_incoming_payload ----------

    def test_normalize_telegram_message(self):
        payload = {
            'message': {
                'message_id': 11,
                'text': 'hello',
                'chat': {'id': 777},
                'from': {'username': 'john'},
            }
        }
        result = normalize_incoming_payload('telegram', payload)
        self.assertIsNotNone(result)
        self.assertEqual(result['chat_id'], '777')
        self.assertEqual(result['username'], 'john')
        self.assertEqual(result['text'], 'hello')

    def test_normalize_telegram_edited_message(self):
        payload = {
            'update_id': 1,
            'edited_message': {
                'message_id': 22,
                'text': 'edited',
                'chat': {'id': 888},
                'from': {'first_name': 'Jane'},
            }
        }
        result = normalize_incoming_payload('telegram', payload)
        self.assertIsNotNone(result)
        self.assertEqual(result['chat_id'], '888')
        self.assertEqual(result['username'], 'Jane')
        self.assertEqual(result['text'], 'edited')

    def test_normalize_telegram_unsupported_update_returns_none(self):
        payload = {'update_id': 1, 'callback_query': {'id': 'q1'}}
        result = normalize_incoming_payload('telegram', payload)
        self.assertIsNone(result)

    def test_normalize_whatsapp(self):
        payload = {'from': '+79990000000', 'name': 'Client', 'body': 'hey'}
        result = normalize_incoming_payload('whatsapp', payload)
        self.assertEqual(result['phone'], '+79990000000')
        self.assertEqual(result['text'], 'hey')

    def test_normalize_max_message_created(self):
        payload = {
            'update_type': 'message_created',
            'message': {
                'sender': {'user_id': 'u42', 'name': 'MaxUser'},
                'recipient': {'chat_id': 'c99'},
                'body': {'text': 'hi', 'mid': 'm1'},
            }
        }
        result = normalize_incoming_payload('max', payload)
        self.assertIsNotNone(result)
        self.assertEqual(result['chat_id'], 'c99')
        self.assertEqual(result['username'], 'MaxUser')
        self.assertEqual(result['text'], 'hi')
        self.assertEqual(result['message_id'], 'm1')

    def test_normalize_max_bot_started_returns_none(self):
        payload = {'update_type': 'bot_started', 'user_id': 'u1'}
        result = normalize_incoming_payload('max', payload)
        self.assertIsNone(result)

    # ---------- route_incoming_message ----------

    def test_route_incoming_creates_session_message_and_deal(self):
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

    def test_route_incoming_ignores_unsupported_update(self):
        payload = {'update_id': 1, 'callback_query': {'id': 'q1'}}
        result = route_incoming_message(self.tenant.id, self.channel.id, payload)
        self.assertEqual(result['status'], 'ignored')

    def test_route_incoming_no_pipeline_sets_error(self):
        Pipeline.objects.all().delete()
        Stage.objects.all().delete()
        payload = {
            'message': {
                'message_id': 13,
                'text': 'No pipeline',
                'chat': {'id': 999},
                'from': {'username': 'bob'},
            }
        }
        result = route_incoming_message(self.tenant.id, self.channel.id, payload)
        self.assertEqual(result['status'], 'ok')
        session = ChatSession.objects.get(external_chat_id='999')
        message = MessageLog.objects.get(chat_session=session)
        self.assertFalse(message.delivered)
        self.assertIn('Воронка или этап не настроены', message.error)
        self.assertEqual(Deal.objects.count(), 0)

    def test_route_incoming_pipeline_without_stage_sets_error(self):
        Stage.objects.all().delete()
        payload = {
            'message': {
                'message_id': 14,
                'text': 'No stage',
                'chat': {'id': 888},
                'from': {'username': 'carol'},
            }
        }
        result = route_incoming_message(self.tenant.id, self.channel.id, payload)
        self.assertEqual(result['status'], 'ok')
        session = ChatSession.objects.get(external_chat_id='888')
        message = MessageLog.objects.get(chat_session=session)
        self.assertFalse(message.delivered)
        self.assertIn('Воронка или этап не настроены', message.error)
        self.assertEqual(Deal.objects.count(), 0)

    def test_route_incoming_auto_create_lead_disabled(self):
        self.channel.auto_create_lead = False
        self.channel.save(update_fields=['auto_create_lead'])
        payload = {
            'message': {
                'message_id': 15,
                'text': 'Disabled',
                'chat': {'id': 777},
                'from': {'username': 'dave'},
            }
        }
        result = route_incoming_message(self.tenant.id, self.channel.id, payload)
        self.assertEqual(result['status'], 'ok')
        session = ChatSession.objects.get(external_chat_id='777')
        self.assertFalse(session.crm_lead_id)
        self.assertEqual(Deal.objects.count(), 0)

    # ---------- route_outgoing_message ----------

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
