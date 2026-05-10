from __future__ import annotations

from unittest.mock import patch, MagicMock

from apps.users.tests.base import TenantAPITestCase


class AIServicesTest(TenantAPITestCase):
    """Tests for AI assistant services and Hermes integration."""

    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='ai_owner@example.com', username='ai_owner')

    def test_get_hermes_profile_for_tenant(self):
        from apps.ai_assistant.services import get_hermes_profile_for_tenant
        self.assertEqual(get_hermes_profile_for_tenant('mycompany'), 'mycompany')

    def test_build_context_for_hermes_no_context(self):
        from apps.ai_assistant.services import build_context_for_hermes
        result = build_context_for_hermes(self.tenant, {})
        self.assertEqual(result, '')

    def test_send_to_hermes_success(self):
        from apps.ai_assistant.services import send_to_hermes

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}]
        }

        with patch('apps.ai_assistant.services.requests.post', return_value=mock_response) as mock_post:
            result = send_to_hermes(
                tenant=self.tenant,
                user=self.owner,
                message='Hello',
                conversation_id='1',
            )
            self.assertEqual(result, 'Test response')
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertEqual(call_args.kwargs['json']['model'], 'qa')

    def test_send_to_hermes_timeout(self):
        import requests
        from apps.ai_assistant.services import send_to_hermes

        with patch('apps.ai_assistant.services.requests.post', side_effect=requests.exceptions.Timeout()):
            result = send_to_hermes(
                tenant=self.tenant,
                user=self.owner,
                message='Hello',
                conversation_id='1',
            )
            self.assertIn('истекло время ожидания', result)


class AIModelsTest(TenantAPITestCase):
    """Tests for AIConversation and AIMessage models."""

    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='ai_model_owner@example.com', username='ai_model_owner')

    def test_create_conversation(self):
        from apps.ai_assistant.models import AIConversation

        conversation = AIConversation.objects.create(
            tenant=self.tenant,
            user=self.owner,
            title='Test conversation',
        )
        self.assertEqual(conversation.title, 'Test conversation')
        self.assertEqual(conversation.tenant, self.tenant)
        self.assertEqual(conversation.user, self.owner)
        self.assertIsNotNone(conversation.created_at)

    def test_create_message(self):
        from apps.ai_assistant.models import AIConversation, AIMessage

        conversation = AIConversation.objects.create(
            tenant=self.tenant,
            user=self.owner,
            title='Test',
        )
        message = AIMessage.objects.create(
            conversation=conversation,
            role='user',
            content='Hello AI',
        )
        self.assertEqual(message.role, 'user')
        self.assertEqual(message.content, 'Hello AI')
        self.assertEqual(message.conversation, conversation)

    def test_conversation_messages_ordering(self):
        from apps.ai_assistant.models import AIConversation, AIMessage

        conversation = AIConversation.objects.create(
            tenant=self.tenant,
            user=self.owner,
        )
        msg1 = AIMessage.objects.create(conversation=conversation, role='user', content='First')
        msg2 = AIMessage.objects.create(conversation=conversation, role='assistant', content='Second')
        msg3 = AIMessage.objects.create(conversation=conversation, role='user', content='Third')

        messages = list(conversation.messages.order_by('created_at'))
        self.assertEqual(messages[0].content, 'First')
        self.assertEqual(messages[1].content, 'Second')
        self.assertEqual(messages[2].content, 'Third')