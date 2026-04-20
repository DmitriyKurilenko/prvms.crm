from __future__ import annotations

import logging
import secrets

import requests

from .models import MessengerChannel

logger = logging.getLogger(__name__)


def register_telegram_webhook(channel: MessengerChannel, webhook_base_url: str, tenant_slug: str) -> tuple[bool, str]:
    """Register webhook URL with Telegram Bot API. Returns (success, detail)."""
    credentials = channel.credentials or {}
    bot_token = credentials.get('bot_token')
    if not bot_token:
        return False, 'bot_token отсутствует'

    # Generate a secret_token for webhook verification if not already set
    secret_token = credentials.get('webhook_token')
    if not secret_token:
        secret_token = secrets.token_urlsafe(32)
        credentials['webhook_token'] = secret_token
        channel.credentials = credentials
        channel.save(update_fields=['credentials'])

    url = f'{webhook_base_url.rstrip("/")}/channels/webhook/{tenant_slug}/telegram/{channel.id}/'
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{bot_token}/setWebhook',
            json={
                'url': url,
                'secret_token': secret_token,
                'allowed_updates': ['message'],
            },
            timeout=15,
        )
        body = resp.json()
        if body.get('ok'):
            return True, body.get('description', 'ok')
        return False, body.get('description', resp.text[:300])
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500]


def unregister_telegram_webhook(bot_token: str) -> tuple[bool, str]:
    """Remove webhook from Telegram Bot API."""
    if not bot_token:
        return False, 'bot_token отсутствует'
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{bot_token}/deleteWebhook',
            timeout=10,
        )
        body = resp.json()
        return bool(body.get('ok')), body.get('description', '')
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]


def get_telegram_webhook_info(bot_token: str) -> dict:
    """Get current webhook info from Telegram Bot API."""
    if not bot_token:
        return {'error': 'bot_token отсутствует'}
    try:
        resp = requests.get(
            f'https://api.telegram.org/bot{bot_token}/getWebhookInfo',
            timeout=10,
        )
        return resp.json().get('result', {})
    except Exception as exc:  # noqa: BLE001
        return {'error': str(exc)[:300]}


MAX_API_BASE = 'https://platform-api.max.ru'


def register_max_webhook(channel: MessengerChannel, webhook_base_url: str, tenant_slug: str) -> tuple[bool, str]:
    """Register webhook URL with MAX Bot API. Returns (success, detail)."""
    credentials = channel.credentials or {}
    bot_token = credentials.get('bot_token')
    if not bot_token:
        return False, 'bot_token отсутствует'

    # Generate a secret for webhook verification if not already set
    secret = credentials.get('webhook_token')
    if not secret:
        secret = secrets.token_urlsafe(32)
        credentials['webhook_token'] = secret
        channel.credentials = credentials
        channel.save(update_fields=['credentials'])

    url = f'{webhook_base_url.rstrip("/")}/channels/webhook/{tenant_slug}/max/{channel.id}/'
    try:
        resp = requests.post(
            f'{MAX_API_BASE}/subscriptions',
            headers={'Authorization': bot_token, 'Content-Type': 'application/json'},
            json={
                'url': url,
                'update_types': ['message_created', 'bot_started'],
                'secret': secret,
            },
            timeout=15,
        )
        body = resp.json()
        if body.get('success'):
            return True, 'Webhook зарегистрирован'
        return False, body.get('message', resp.text[:300])
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500]


def unregister_max_webhook(channel: MessengerChannel) -> tuple[bool, str]:
    """Remove webhook subscription from MAX Bot API."""
    credentials = channel.credentials or {}
    bot_token = credentials.get('bot_token')
    if not bot_token:
        return False, 'bot_token отсутствует'
    try:
        resp = requests.delete(
            f'{MAX_API_BASE}/subscriptions',
            headers={'Authorization': bot_token},
            params={'url': credentials.get('webhook_url', '')},
            timeout=10,
        )
        body = resp.json()
        return bool(body.get('success')), body.get('message', '')
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]


def get_max_webhook_info(bot_token: str) -> dict:
    """Get current webhook subscriptions from MAX Bot API."""
    if not bot_token:
        return {'error': 'bot_token отсутствует'}
    try:
        resp = requests.get(
            f'{MAX_API_BASE}/subscriptions',
            headers={'Authorization': bot_token},
            timeout=10,
        )
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {'error': str(exc)[:300]}


def normalize_incoming_payload(channel_type: str, payload: dict) -> dict:
    if channel_type == 'telegram':
        message = payload.get('message') or payload
        sender = message.get('from', {})
        chat = message.get('chat', {})
        return {
            'chat_id': str(chat.get('id') or payload.get('chat_id') or payload.get('from') or 'unknown'),
            'username': sender.get('username') or sender.get('first_name') or payload.get('username') or '',
            'phone': payload.get('phone', ''),
            'text': message.get('text') or payload.get('text') or '',
            'message_id': str(message.get('message_id') or payload.get('message_id') or ''),
            'attachments': payload.get('attachments') or [],
        }

    if channel_type in {'whatsapp', 'whatsapp_business'}:
        return {
            'chat_id': str(payload.get('chat_id') or payload.get('from') or 'unknown'),
            'username': payload.get('name') or payload.get('username') or '',
            'phone': payload.get('from') or payload.get('phone') or '',
            'text': payload.get('text') or payload.get('body') or '',
            'message_id': str(payload.get('message_id') or payload.get('id') or ''),
            'attachments': payload.get('attachments') or [],
        }

    if channel_type == 'max':
        # MAX Update: {update_type, timestamp, message: {sender, recipient, timestamp, body, ...}}
        message = payload.get('message') or {}
        sender = message.get('sender') or {}
        recipient = message.get('recipient') or {}
        body = message.get('body') or {}
        # chat_id: recipient.chat_id for group chats, sender.user_id for direct
        chat_id = str(
            recipient.get('chat_id')
            or sender.get('user_id')
            or payload.get('chat_id')
            or 'unknown'
        )
        return {
            'chat_id': chat_id,
            'username': sender.get('name') or sender.get('username') or '',
            'phone': '',
            'text': body.get('text') or '',
            'message_id': str(body.get('mid') or message.get('timestamp') or ''),
            'attachments': body.get('attachments') or [],
        }

    return {
        'chat_id': str(payload.get('chat_id') or payload.get('from') or 'unknown'),
        'username': payload.get('username') or '',
        'phone': payload.get('phone') or '',
        'text': payload.get('text') or '',
        'message_id': str(payload.get('message_id') or payload.get('id') or ''),
        'attachments': payload.get('attachments') or [],
    }


def send_outgoing(channel: MessengerChannel, external_chat_id: str, text: str, attachments: list | None = None) -> tuple[bool, str]:
    credentials = channel.credentials or {}
    attachments = attachments or []

    try:
        if channel.channel_type == 'telegram':
            bot_token = credentials.get('bot_token')
            if not bot_token:
                return False, 'Telegram bot_token is missing'
            response = requests.post(
                f'https://api.telegram.org/bot{bot_token}/sendMessage',
                json={'chat_id': external_chat_id, 'text': text},
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
            return bool(body.get('ok')), str((body.get('result') or {}).get('message_id', ''))

        if channel.channel_type in {'whatsapp', 'whatsapp_business'}:
            endpoint = credentials.get('send_url')
            if not endpoint:
                return False, 'WhatsApp send_url is missing'
            payload = {'chat_id': external_chat_id, 'text': text, 'attachments': attachments}
            headers = {}
            if credentials.get('auth_token'):
                headers['Authorization'] = f'Bearer {credentials["auth_token"]}'
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            body = response.json() if response.text else {}
            return True, str(body.get('message_id', ''))

        if channel.channel_type == 'max':
            bot_token = credentials.get('bot_token')
            if not bot_token:
                return False, 'MAX bot_token is missing'
            params = {'chat_id': int(external_chat_id)} if external_chat_id.isdigit() else {'chat_id': external_chat_id}
            response = requests.post(
                f'{MAX_API_BASE}/messages',
                headers={'Authorization': bot_token, 'Content-Type': 'application/json'},
                params=params,
                json={'text': text},
                timeout=10,
            )
            response.raise_for_status()
            body = response.json() if response.text else {}
            msg = body.get('message', {})
            return True, str(msg.get('body', {}).get('mid', ''))

        return False, f'Unsupported channel type: {channel.channel_type}'
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500]
