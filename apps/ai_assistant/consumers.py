from __future__ import annotations

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django_tenants.utils import schema_context

from apps.tenants.models import Tenant
from apps.users.models import Membership

logger = logging.getLogger(__name__)


class AIAssistantConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not getattr(user, 'is_authenticated', False):
            await self.close(code=4401)
            return

        self._user = user
        slug_hint = (self.scope.get('tenant_slug') or '').strip().lower()
        self._tenant_schema = await self._resolve_tenant_schema(user.id, slug_hint)

        if not self._tenant_schema:
            await self.close(code=4400)
            return

        self.group_name = f'ai.user.{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'connected', 'user_id': user.id})

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'ping':
            await self.send_json({'type': 'pong'})
        elif action == 'message':
            await self._handle_message(content)

    async def ai_message(self, event):
        await self.send_json(event['payload'])

    async def _handle_message(self, content: dict):
        from .services import send_to_hermes
        from .models import AIConversation, AIMessage
        from django.utils import timezone

        message = content.get('message', '')
        conversation_id = content.get('conversation_id')
        context_data = content.get('context', {})

        if not message:
            await self.send_json({'type': 'error', 'message': 'Empty message'})
            return

        tenant = await self._get_tenant()
        if not tenant:
            await self.send_json({'type': 'error', 'message': 'Tenant not found'})
            return

        conversation = None
        if conversation_id:
            conversation = await self._get_conversation(conversation_id, tenant)

        if not conversation:
            conversation = await self._create_conversation(tenant, context_data)

        await self._save_message(conversation, 'user', message)

        ai_content = await database_sync_to_async(send_to_hermes)(
            tenant=tenant,
            user=self._user,
            message=message,
            conversation_id=str(conversation.id),
            context=context_data,
        )

        ai_message = await self._save_message(conversation, 'assistant', ai_content)

        await database_sync_to_async(
            lambda: self._update_conversation_time(conversation)
        )()

        await self.send_json({
            'type': 'ai_response',
            'conversation_id': conversation.id,
            'message_id': ai_message.id,
            'content': ai_content,
            'role': 'assistant',
        })

    @staticmethod
    @database_sync_to_async
    def _resolve_tenant_schema(user_id: int, slug_hint: str) -> str:
        with schema_context('public'):
            qs = Tenant.objects.filter(is_active=True)
            if slug_hint:
                tenant = qs.filter(slug=slug_hint).first()
                if tenant:
                    membership = Membership.objects.filter(
                        user_id=user_id,
                        tenant_id=tenant.id,
                        is_active=True,
                        joined_at__isnull=False,
                        invite_token__isnull=True,
                    ).first()
                    if membership:
                        return tenant.schema_name
            membership = (
                Membership.objects.filter(
                    user_id=user_id,
                    is_active=True,
                    joined_at__isnull=False,
                    invite_token__isnull=True,
                )
                .select_related('tenant')
                .order_by('tenant_id')
                .first()
            )
            if membership and membership.tenant and membership.tenant.is_active:
                return membership.tenant.schema_name
        return ''

    async def _get_tenant(self):
        with schema_context('public'):
            return Tenant.objects.filter(schema_name=self._tenant_schema, is_active=True).first()

    async def _get_conversation(self, conversation_id: int, tenant):
        with schema_context(self._tenant_schema):
            return AIConversation.objects.filter(
                id=conversation_id,
                tenant_id=tenant.id,
                user_id=self._user.id,
            ).first()

    async def _create_conversation(self, tenant, context_data: dict):
        with schema_context(self._tenant_schema):
            return AIConversation.objects.create(
                tenant_id=tenant.id,
                user_id=self._user.id,
                channel_id=context_data.get('channel_id'),
                deal_id=context_data.get('deal_id'),
                title='Новый диалог',
            )

    async def _save_message(self, conversation, role: str, content: str):
        with schema_context(self._tenant_schema):
            return AIMessage.objects.create(
                conversation=conversation,
                role=role,
                content=content,
            )

    @staticmethod
    def _update_conversation_time(conversation):
        from django.utils import timezone
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])