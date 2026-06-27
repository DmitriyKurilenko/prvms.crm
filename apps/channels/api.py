from __future__ import annotations

import logging

from django.conf import settings
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_feature_access, require_roles
from apps.core.tenant import get_request_tenant

from .models import ChatSession, MessageLog, MessengerChannel
from .providers import (
    get_max_webhook_info,
    get_telegram_webhook_info,
    get_vk_callback_info,
    register_max_webhook,
    register_telegram_webhook,
    register_vk_callback,
    unregister_max_webhook,
    unregister_telegram_webhook,
    unregister_vk_callback,
)
from .tasks import route_outgoing_message

logger = logging.getLogger(__name__)
messenger_channels_router = Router(tags=['channels'], auth=JWTAuth())


class ChannelIn(Schema):
    name: str
    channel_type: str
    credentials: dict = {}
    crm_channel_id: str = ''
    auto_create_lead: bool = True
    welcome_message: str = ''
    is_active: bool = True


class ChannelPatchIn(Schema):
    name: str | None = None
    channel_type: str | None = None
    credentials: dict | None = None
    crm_channel_id: str | None = None
    auto_create_lead: bool | None = None
    welcome_message: str | None = None
    is_active: bool | None = None


class SendMessageIn(Schema):
    chat_session_id: int
    text: str
    attachments: list[dict] = []


@messenger_channels_router.get('/')
def list_channels(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'messenger_channels')
    return [
        {
            'id': c.id,
            'name': c.name,
            'channel_type': c.channel_type,
            'credentials': c.credentials or {},
            'status': c.status,
            'status_detail': c.status_detail,
            'auto_create_lead': c.auto_create_lead,
            'welcome_message': c.welcome_message,
            'is_active': c.is_active,
        }
        for c in MessengerChannel.objects.all().order_by('-id')
    ]


@messenger_channels_router.post('/')
def create_channel(request, payload: ChannelIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'messenger_channels')
    c = MessengerChannel.objects.create(**payload.dict())
    # Auto-register webhook for Telegram
    if c.channel_type == 'telegram' and c.is_active:
        _try_register_telegram(c)
    # Auto-register webhook for MAX
    elif c.channel_type == 'max' and c.is_active:
        _try_register_max(c)
    # Auto-register webhook for VK
    elif c.channel_type == 'vk' and c.is_active:
        _try_register_vk(c)
    return {'id': c.id, 'status': c.status, 'status_detail': c.status_detail}


@messenger_channels_router.patch('/{channel_id}/')
def patch_channel(request, channel_id: int, payload: ChannelPatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'messenger_channels')
    data = payload.dict(exclude_unset=True)
    MessengerChannel.objects.filter(id=channel_id).update(**data)
    c = MessengerChannel.objects.filter(id=channel_id).first()
    # Re-register webhook for Telegram on credential/active changes
    if c and c.channel_type == 'telegram' and ('credentials' in data or 'is_active' in data):
        if c.is_active:
            _try_register_telegram(c)
        else:
            bot_token = (c.credentials or {}).get('bot_token', '')
            unregister_telegram_webhook(bot_token)
            c.status = 'disabled'
            c.status_detail = 'Канал деактивирован'
            c.save(update_fields=['status', 'status_detail'])
    # Re-register webhook for MAX on credential/active changes
    if c and c.channel_type == 'max' and ('credentials' in data or 'is_active' in data):
        if c.is_active:
            _try_register_max(c)
        else:
            unregister_max_webhook(c)
            c.status = 'disabled'
            c.status_detail = 'Канал деактивирован'
            c.save(update_fields=['status', 'status_detail'])
    # Re-register webhook for VK on credential/active changes
    if c and c.channel_type == 'vk' and ('credentials' in data or 'is_active' in data):
        if c.is_active:
            _try_register_vk(c)
        else:
            unregister_vk_callback(c)
            c.status = 'disabled'
            c.status_detail = 'Канал деактивирован'
            c.save(update_fields=['status', 'status_detail'])
    return {'detail': 'ok'}


@messenger_channels_router.delete('/{channel_id}/')
def delete_channel(request, channel_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'messenger_channels')
    c = MessengerChannel.objects.filter(id=channel_id).first()
    if c and c.channel_type == 'telegram':
        bot_token = (c.credentials or {}).get('bot_token', '')
        unregister_telegram_webhook(bot_token)
    if c and c.channel_type == 'max':
        unregister_max_webhook(c)
    if c and c.channel_type == 'vk':
        unregister_vk_callback(c)
    MessengerChannel.objects.filter(id=channel_id).delete()
    return {'detail': 'deleted'}


@messenger_channels_router.get('/{channel_id}/stats/')
def channel_stats(request, channel_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'messenger_channels')
    sessions = ChatSession.objects.filter(channel_id=channel_id)
    messages = MessageLog.objects.filter(chat_session__channel_id=channel_id)
    return {'sessions': sessions.count(), 'messages': messages.count(), 'active_sessions': sessions.filter(is_active=True).count()}


@messenger_channels_router.get('/{channel_id}/chats/')
def channel_chats(request, channel_id: int):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'messenger_channels')
    return [
        {
            'id': chat.id,
            'external_chat_id': chat.external_chat_id,
            'external_user_name': chat.external_user_name,
            'crm_contact_id': chat.crm_contact_id,
            'crm_chat_id': chat.crm_chat_id,
            'crm_lead_id': chat.crm_lead_id,
            'is_active': chat.is_active,
            'last_message_at': chat.last_message_at.isoformat(),
        }
        for chat in ChatSession.objects.filter(channel_id=channel_id).order_by('-last_message_at')
    ]


@messenger_channels_router.get('/{channel_id}/chats/{chat_id}/messages/')
def chat_messages(request, channel_id: int, chat_id: int):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'messenger_channels')
    rows = MessageLog.objects.filter(chat_session_id=chat_id, chat_session__channel_id=channel_id).order_by('created_at')
    return [
        {
            'id': m.id,
            'direction': m.direction,
            'text': m.text,
            'attachments': m.attachments,
            'external_message_id': m.external_message_id,
            'crm_message_id': m.crm_message_id,
            'delivered': m.delivered,
            'error': m.error,
            'created_at': m.created_at.isoformat(),
        }
        for m in rows
    ]


@messenger_channels_router.post('/{channel_id}/send/')
def send_message(request, channel_id: int, payload: SendMessageIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'messenger_channels')
    tenant = get_request_tenant(request)
    route_outgoing_message.delay(
        tenant.id,
        channel_id,
        payload.chat_session_id,
        {
            'text': payload.text,
            'attachments': payload.attachments,
            'source': 'manual',
        },
    )
    return {'detail': 'queued'}


@messenger_channels_router.post('/{channel_id}/register-webhook/')
def register_webhook(request, channel_id: int):
    """Manually trigger webhook registration (e.g. after changing WEBHOOK_BASE_URL)."""
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'messenger_channels')
    c = MessengerChannel.objects.filter(id=channel_id).first()
    if not c:
        return {'detail': 'not found'}
    if c.channel_type == 'telegram':
        _try_register_telegram(c)
    elif c.channel_type == 'max':
        _try_register_max(c)
    elif c.channel_type == 'vk':
        _try_register_vk(c)
    else:
        return {'detail': 'этот тип канала не поддерживает авто-регистрацию webhook'}
    c.refresh_from_db()
    return {'status': c.status, 'status_detail': c.status_detail}


@messenger_channels_router.get('/{channel_id}/webhook-info/')
def webhook_info(request, channel_id: int):
    """Get current webhook status from Telegram API."""
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'messenger_channels')
    c = MessengerChannel.objects.filter(id=channel_id).first()
    if not c:
        return {'detail': 'not found'}
    bot_token = (c.credentials or {}).get('bot_token', '')
    if c.channel_type == 'telegram':
        return get_telegram_webhook_info(bot_token)
    if c.channel_type == 'max':
        return get_max_webhook_info(bot_token)
    if c.channel_type == 'vk':
        credentials = c.credentials or {}
        return get_vk_callback_info(credentials.get('access_token', ''), credentials.get('group_id', ''))
    return {'detail': 'этот тип канала не поддерживает запрос статуса webhook'}


def _try_register_telegram(channel: MessengerChannel) -> None:
    """Try to register Telegram webhook. Update channel status accordingly."""
    from django.db import connection
    base_url = getattr(settings, 'WEBHOOK_BASE_URL', '')
    if not base_url:
        channel.status = 'error'
        channel.status_detail = 'WEBHOOK_BASE_URL не настроен в .env'
        channel.save(update_fields=['status', 'status_detail'])
        logger.warning('WEBHOOK_BASE_URL not set, cannot register Telegram webhook for channel %s', channel.id)
        return
    tenant_slug = connection.tenant.slug if hasattr(connection, 'tenant') and connection.tenant else ''
    if not tenant_slug:
        channel.status = 'error'
        channel.status_detail = 'Не удалось определить tenant для формирования URL'
        channel.save(update_fields=['status', 'status_detail'])
        return
    ok, detail = register_telegram_webhook(channel, base_url, tenant_slug)
    if ok:
        channel.status = 'active'
        channel.status_detail = f'Webhook зарегистрирован: {detail}'
    else:
        channel.status = 'error'
        channel.status_detail = f'Ошибка регистрации webhook: {detail}'
    channel.save(update_fields=['status', 'status_detail'])


def _try_register_max(channel: MessengerChannel) -> None:
    """Try to register MAX webhook. Update channel status accordingly."""
    from django.db import connection
    base_url = getattr(settings, 'WEBHOOK_BASE_URL', '')
    if not base_url:
        channel.status = 'error'
        channel.status_detail = 'WEBHOOK_BASE_URL не настроен в .env'
        channel.save(update_fields=['status', 'status_detail'])
        logger.warning('WEBHOOK_BASE_URL not set, cannot register MAX webhook for channel %s', channel.id)
        return
    tenant_slug = connection.tenant.slug if hasattr(connection, 'tenant') and connection.tenant else ''
    if not tenant_slug:
        channel.status = 'error'
        channel.status_detail = 'Не удалось определить tenant для формирования URL'
        channel.save(update_fields=['status', 'status_detail'])
        return
    ok, detail = register_max_webhook(channel, base_url, tenant_slug)
    if ok:
        channel.status = 'active'
        channel.status_detail = f'Webhook зарегистрирован: {detail}'
    else:
        channel.status = 'error'
        channel.status_detail = f'Ошибка регистрации webhook: {detail}'
    channel.save(update_fields=['status', 'status_detail'])


def _try_register_vk(channel: MessengerChannel) -> None:
    """Try to register VK callback. Update channel status accordingly."""
    from django.db import connection
    base_url = getattr(settings, 'WEBHOOK_BASE_URL', '')
    if not base_url:
        channel.status = 'error'
        channel.status_detail = 'WEBHOOK_BASE_URL не настроен в .env'
        channel.save(update_fields=['status', 'status_detail'])
        logger.warning('WEBHOOK_BASE_URL not set, cannot register VK callback for channel %s', channel.id)
        return
    tenant_slug = connection.tenant.slug if hasattr(connection, 'tenant') and connection.tenant else ''
    if not tenant_slug:
        channel.status = 'error'
        channel.status_detail = 'Не удалось определить tenant для формирования URL'
        channel.save(update_fields=['status', 'status_detail'])
        return
    ok, detail = register_vk_callback(channel, base_url, tenant_slug)
    if ok:
        channel.status = 'active'
        channel.status_detail = f'Callback зарегистрирован: {detail}'
    else:
        channel.status = 'error'
        channel.status_detail = f'Ошибка регистрации callback: {detail}'
    channel.save(update_fields=['status', 'status_detail'])
