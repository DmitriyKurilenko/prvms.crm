from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from ninja_jwt.tokens import AccessToken

from apps.users.models import User


@database_sync_to_async
def _get_user_by_access_token(token: str):
    try:
        payload = AccessToken(token)
        user_id = payload.get('user_id')
        if not user_id:
            return AnonymousUser()
        return User.objects.filter(id=user_id, is_active=True).first() or AnonymousUser()
    except Exception:
        return AnonymousUser()


class JWTQueryAuthMiddleware(BaseMiddleware):
    """
    Authenticates WebSocket connections via query param token:
    ws://.../ws/notifications/?token=<access_token>&slug=<tenant_slug>
    """

    async def __call__(self, scope, receive, send):
        scope['user'] = AnonymousUser()
        scope['tenant_slug'] = ''
        query_string = (scope.get('query_string') or b'').decode('utf-8')
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
        if token:
            scope['user'] = await _get_user_by_access_token(token)
        slug = params.get('slug', [None])[0]
        if slug:
            scope['tenant_slug'] = slug
        return await super().__call__(scope, receive, send)
