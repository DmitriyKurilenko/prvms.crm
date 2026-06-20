from __future__ import annotations

import secrets

from django.conf import settings
from django.core import signing
from django.db import connection
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_roles
from apps.core.tenant import get_request_tenant

from .models import MessengerChannel
from .providers import get_vk_group_info, register_vk_callback

vk_oauth_router = Router(tags=['channels'], auth=JWTAuth())


class VkStartOut(Schema):
    authorize_url: str
    state: str


class VkTokenIn(Schema):
    group_id: int
    access_token: str


class VkCompleteIn(Schema):
    state: str
    tokens: list[VkTokenIn]


class CreatedItem(Schema):
    channel_id: int
    group_id: int
    name: str


class FailedItem(Schema):
    group_id: int
    error: str


class VkCompleteOut(Schema):
    created: list[CreatedItem]
    failed: list[FailedItem]


@vk_oauth_router.post('/start/', response={200: VkStartOut})
def vk_start(request):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    app_id = getattr(settings, 'VK_APP_ID', '')
    if not app_id:
        return 400, {'detail': 'VK_APP_ID не настроен'}

    state = signing.dumps(
        {'tenant_id': tenant.id, 'user_id': request.user.id, 'nonce': secrets.token_urlsafe(16)},
        salt='vk-channel-oauth',
    )

    redirect_uri = f"{getattr(settings, 'FRONTEND_APP_URL', '').rstrip('/')}/oauth/vk/callback"
    authorize_url = (
        'https://oauth.vk.com/authorize?'
        f'client_id={app_id}&'
        'display=page&'
        'scope=messages,groups&'
        'response_type=token&'
        f'redirect_uri={redirect_uri}&'
        'v=5.199&'
        f'state={state}'
    )
    return {'authorize_url': authorize_url, 'state': state}


@vk_oauth_router.post('/complete/', response={200: VkCompleteOut, 400: dict})
def vk_complete(request, payload: VkCompleteIn):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)

    try:
        state = signing.loads(payload.state, salt='vk-channel-oauth', max_age=3600)
    except signing.BadSignature:
        return 400, {'detail': 'Invalid or expired state'}

    if state.get('tenant_id') != tenant.id:
        return 400, {'detail': 'State tenant mismatch'}

    webhook_base_url = getattr(settings, 'WEBHOOK_BASE_URL', '')
    if not webhook_base_url:
        return 400, {'detail': 'WEBHOOK_BASE_URL не настроен'}

    tenant_slug = connection.tenant.slug if hasattr(connection, 'tenant') and connection.tenant else tenant.slug
    created: list[CreatedItem] = []
    failed: list[FailedItem] = []
    app_id = getattr(settings, 'VK_APP_ID', '')

    for token_item in payload.tokens:
        group_id = token_item.group_id
        access_token = token_item.access_token

        group_info = get_vk_group_info(access_token, group_id)
        if group_info.get('error'):
            failed.append({'group_id': group_id, 'error': group_info['error']})
            continue

        name = group_info.get('name') or f'VK {group_id}'
        channel = MessengerChannel.objects.create(
            channel_type='vk',
            name=name,
            credentials={'group_id': group_id, 'access_token': access_token, 'app_id': app_id},
            status='active',
            auto_create_lead=True,
            is_active=True,
        )

        ok, detail = register_vk_callback(channel, webhook_base_url, tenant_slug)
        if ok:
            created.append({'channel_id': channel.id, 'group_id': group_id, 'name': name})
        else:
            channel.delete()
            failed.append({'group_id': group_id, 'error': detail})

    return {'created': created, 'failed': failed}
