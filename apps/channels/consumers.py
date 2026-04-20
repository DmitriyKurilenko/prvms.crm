from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time chat updates.
    Requires tenant_slug in scope (set by JWTQueryAuthMiddleware from ?slug= param).

    Client subscribes to a channel by sending:
        {"action": "subscribe", "channel_id": 5}
    Then receives events:
        {"type": "chat.message", "message": {...}}
        {"type": "chat.session_update", "session": {...}}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscribed_groups: set[str] = set()
        self.tenant_slug: str = ''

    async def connect(self):
        user = self.scope.get('user')
        if not user or not getattr(user, 'is_authenticated', False):
            await self.close(code=4401)
            return
        self.tenant_slug = self.scope.get('tenant_slug', '')
        if not self.tenant_slug:
            await self.close(code=4400)
            return
        await self.accept()
        await self.send_json({'type': 'connected'})

    def _group_name(self, channel_id: int) -> str:
        return f'chat.{self.tenant_slug}.channel.{channel_id}'

    async def disconnect(self, close_code):
        for group in self.subscribed_groups:
            await self.channel_layer.group_discard(group, self.channel_name)
        self.subscribed_groups.clear()

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'ping':
            await self.send_json({'type': 'pong'})
        elif action == 'subscribe':
            channel_id = content.get('channel_id')
            if channel_id is not None:
                group = self._group_name(channel_id)
                if group not in self.subscribed_groups:
                    await self.channel_layer.group_add(group, self.channel_name)
                    self.subscribed_groups.add(group)
                    await self.send_json({'type': 'subscribed', 'channel_id': channel_id})
        elif action == 'unsubscribe':
            channel_id = content.get('channel_id')
            if channel_id is not None:
                group = self._group_name(channel_id)
                if group in self.subscribed_groups:
                    await self.channel_layer.group_discard(group, self.channel_name)
                    self.subscribed_groups.discard(group)

    # ── group broadcast handlers ──

    async def chat_message(self, event):
        """New message in a channel's chat session."""
        await self.send_json(event['payload'])

    async def chat_session_update(self, event):
        """Session created or updated."""
        await self.send_json(event['payload'])
