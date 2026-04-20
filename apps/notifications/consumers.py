from __future__ import annotations

import asyncio
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django_tenants.utils import schema_context

from apps.tenants.models import Tenant
from apps.users.models import Membership

from .presence import PRESENCE_TTL_SECONDS, mark_offline, mark_online

logger = logging.getLogger(__name__)


PRESENCE_REFRESH_INTERVAL = max(10, PRESENCE_TTL_SECONDS // 2)


class NotificationsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not getattr(user, 'is_authenticated', False):
            await self.close(code=4401)
            return
        self.group_name = f'notifications.user.{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'connected', 'user_id': user.id})

        slug_hint = (self.scope.get('tenant_slug') or '').strip().lower()
        self._tenant_schema = await self._resolve_tenant_schema(user.id, slug_hint)
        self._presence_user_id = user.id
        self._presence_task = None
        if self._tenant_schema:
            await database_sync_to_async(mark_online)(self._tenant_schema, user.id)
            self._presence_task = asyncio.create_task(self._presence_heartbeat())

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        task = getattr(self, '_presence_task', None)
        if task is not None and not task.done():
            task.cancel()
        tenant_schema = getattr(self, '_tenant_schema', '')
        user_id = getattr(self, '_presence_user_id', None)
        if tenant_schema and user_id:
            await database_sync_to_async(mark_offline)(tenant_schema, user_id)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'ping':
            await self.send_json({'type': 'pong'})
            tenant_schema = getattr(self, '_tenant_schema', '')
            user_id = getattr(self, '_presence_user_id', None)
            if tenant_schema and user_id:
                await database_sync_to_async(mark_online)(tenant_schema, user_id)

    async def notification_message(self, event):
        await self.send_json(event['payload'])

    async def _presence_heartbeat(self) -> None:
        try:
            while True:
                await asyncio.sleep(PRESENCE_REFRESH_INTERVAL)
                tenant_schema = getattr(self, '_tenant_schema', '')
                user_id = getattr(self, '_presence_user_id', None)
                if not tenant_schema or not user_id:
                    return
                await database_sync_to_async(mark_online)(tenant_schema, user_id)
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            logger.warning('presence heartbeat failed', exc_info=True)

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
