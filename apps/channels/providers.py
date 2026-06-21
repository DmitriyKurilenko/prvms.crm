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
                'allowed_updates': ['message', 'edited_message'],
            },
            timeout=15,
        )
        body = resp.json()
        if body.get('ok'):
            return True, body.get('description', 'ok')
        return False, body.get('description', resp.text[:300])
    except requests.RequestException as exc:
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
    except requests.RequestException as exc:
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
    except requests.RequestException as exc:
        return {'error': str(exc)[:300]}


MAX_API_BASE = 'https://platform-api.max.ru'
VK_API_VERSION = '5.199'


def get_vk_group_info(access_token: str, group_id: int | str) -> dict:
    """Get group name and photo from VK API."""
    try:
        resp = requests.get(
            'https://api.vk.com/method/groups.getById',
            params={'group_id': group_id, 'access_token': access_token, 'v': VK_API_VERSION},
            timeout=10,
        )
        body = resp.json()
        if body.get('response'):
            g = body['response'][0]
            return {'name': g.get('name', ''), 'photo_200': g.get('photo_200', '')}
        return {'error': body.get('error', {}).get('error_msg', 'unknown')}
    except requests.RequestException as exc:
        return {'error': str(exc)[:300]}


def register_vk_callback(channel: MessengerChannel, webhook_base_url: str, tenant_slug: str) -> tuple[bool, str]:
    """Register VK Callback API server. Returns (success, detail)."""
    credentials = channel.credentials or {}
    access_token = credentials.get('access_token')
    group_id = credentials.get('group_id')
    if not access_token or not group_id:
        return False, 'access_token или group_id отсутствуют'

    # 1. Get confirmation code
    try:
        resp = requests.get(
            'https://api.vk.com/method/groups.getCallbackConfirmationCode',
            params={'group_id': group_id, 'access_token': access_token, 'v': VK_API_VERSION},
            timeout=10,
        )
        body = resp.json()
        if not body.get('response'):
            return False, body.get('error', {}).get('error_msg', 'failed to get confirmation code')
        credentials['confirmation_code'] = body['response']['code']
    except requests.RequestException as exc:
        return False, str(exc)[:500]

    # 2. Generate secret key
    secret_key = secrets.token_urlsafe(32)
    credentials['secret_key'] = secret_key

    # 3. Add callback server
    url = f'{webhook_base_url.rstrip("/")}/channels/webhook/{tenant_slug}/vk/{channel.id}/'
    try:
        resp = requests.get(
            'https://api.vk.com/method/groups.addCallbackServer',
            params={
                'group_id': group_id,
                'url': url,
                'title': 'PRVMS CRM',
                'secret_key': secret_key,
                'access_token': access_token,
                'v': VK_API_VERSION,
            },
            timeout=10,
        )
        body = resp.json()
        if not body.get('response'):
            return False, body.get('error', {}).get('error_msg', 'failed to add callback server')
        credentials['server_id'] = body['response']['server_id']
    except requests.RequestException as exc:
        return False, str(exc)[:500]

    # 4. Set callback settings
    try:
        resp = requests.get(
            'https://api.vk.com/method/groups.setCallbackSettings',
            params={
                'group_id': group_id,
                'server_id': credentials['server_id'],
                'message_new': 1,
                'access_token': access_token,
                'v': VK_API_VERSION,
            },
            timeout=10,
        )
        body = resp.json()
        if body.get('response') != 1:
            return False, body.get('error', {}).get('error_msg', 'failed to set callback settings')
    except requests.RequestException as exc:
        return False, str(exc)[:500]

    channel.credentials = credentials
    channel.save(update_fields=['credentials'])
    return True, 'ok'


def unregister_vk_callback(channel: MessengerChannel) -> tuple[bool, str]:
    """Remove VK Callback API server."""
    credentials = channel.credentials or {}
    access_token = credentials.get('access_token')
    group_id = credentials.get('group_id')
    server_id = credentials.get('server_id')
    if not access_token or not group_id or not server_id:
        return False, 'access_token, group_id или server_id отсутствуют'
    try:
        resp = requests.get(
            'https://api.vk.com/method/groups.deleteCallbackServer',
            params={'group_id': group_id, 'server_id': server_id, 'access_token': access_token, 'v': VK_API_VERSION},
            timeout=10,
        )
        body = resp.json()
        return bool(body.get('response') == 1), body.get('error', {}).get('error_msg', '')
    except requests.RequestException as exc:
        return False, str(exc)[:300]


def get_vk_callback_info(access_token: str, group_id: int | str) -> dict:
    """Get VK callback servers info."""
    try:
        resp = requests.get(
            'https://api.vk.com/method/groups.getCallbackServers',
            params={'group_id': group_id, 'access_token': access_token, 'v': VK_API_VERSION},
            timeout=10,
        )
        return resp.json()
    except requests.RequestException as exc:
        return {'error': str(exc)[:300]}


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
    except requests.RequestException as exc:
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
    except requests.RequestException as exc:
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
    except requests.RequestException as exc:
        return {'error': str(exc)[:300]}


def normalize_incoming_payload(channel_type: str, payload: dict) -> dict | None:
    """Extract chat_id, username, text, etc. from a provider-specific webhook payload.

    Returns *None* when the payload should be ignored (e.g. MAX ``bot_started``
    or an unsupported Telegram update type).
    """
    if channel_type == 'telegram':
        # Telegram sends the whole Update object.  We care about *message*
        # and *edited_message*; everything else is ignored.
        message = payload.get('message') or payload.get('edited_message')
        if not message:
            return None
        sender = message.get('from', {})
        chat = message.get('chat', {})
        return {
            'chat_id': str(chat.get('id') or 'unknown'),
            'username': sender.get('username') or sender.get('first_name') or '',
            'phone': payload.get('phone', ''),
            'text': message.get('text') or payload.get('text') or '',
            'message_id': str(message.get('message_id') or ''),
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
        # MAX sends {update_type, timestamp, message: {...}}
        update_type = payload.get('update_type', '')
        if update_type not in {'message_created', 'bot_started'}:
            return None
        # bot_started has no chat text — ignore for message routing
        if update_type == 'bot_started':
            return None
        message = payload.get('message') or {}
        sender = message.get('sender') or {}
        recipient = message.get('recipient') or {}
        body = message.get('body') or {}
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

    if channel_type == 'vk':
        if payload.get('type') != 'message_new':
            return None
        message = payload.get('object', {}).get('message') or {}
        return {
            'chat_id': str(message.get('peer_id') or message.get('from_id') or 'unknown'),
            'username': '',
            'phone': '',
            'text': message.get('text') or '',
            'message_id': str(message.get('id') or ''),
            'attachments': message.get('attachments') or [],
        }

    if channel_type == 'email':
        # Payload формирует email_poller.fetch_new_messages: письмо → нормализованный диалог.
        from_email = str(payload.get('from_email') or '')
        if not from_email:
            return None
        subject = str(payload.get('subject') or '')
        body = str(payload.get('text') or '')
        text = f'{subject}\n\n{body}'.strip() if subject else body
        return {
            'chat_id': from_email,
            'username': str(payload.get('from_name') or from_email),
            'phone': '',
            'text': text,
            'message_id': str(payload.get('message_id') or ''),
            'attachments': payload.get('attachments') or [],
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

        if channel.channel_type == 'vk':
            access_token = credentials.get('access_token')
            if not access_token:
                return False, 'VK access_token is missing'
            try:
                response = requests.post(
                    'https://api.vk.com/method/messages.send',
                    data={
                        'peer_id': external_chat_id,
                        'message': text,
                        'random_id': secrets.randbits(31),
                        'access_token': access_token,
                        'v': VK_API_VERSION,
                    },
                    timeout=10,
                )
                body = response.json()
                if body.get('response'):
                    return True, str(body['response'])
                return False, body.get('error', {}).get('error_msg', 'unknown')
            except requests.RequestException as exc:
                return False, str(exc)[:500]

        if channel.channel_type == 'email':
            return _send_email(credentials, external_chat_id, text)

        return False, f'Unsupported channel type: {channel.channel_type}'
    except requests.RequestException as exc:
        return False, str(exc)[:500]


def _send_email(credentials: dict, to_email: str, text: str) -> tuple[bool, str]:
    """Отправка ответа письмом через per-channel SMTP. Стык [граница]: реальный SMTP."""
    import smtplib

    from django.core.mail import EmailMessage, get_connection

    host = credentials.get('smtp_host', '')
    if not host or not to_email:
        return False, 'SMTP host or recipient is missing'
    use_ssl = bool(credentials.get('smtp_ssl', True))
    from_name = str(credentials.get('from_name') or '')
    username = credentials.get('username', '')
    from_email = f'{from_name} <{username}>' if from_name else username
    try:
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=host,
            port=int(credentials.get('smtp_port', 465)),
            username=username,
            password=credentials.get('password', ''),
            use_ssl=use_ssl,
            use_tls=not use_ssl,
        )
        message = EmailMessage(
            subject=str(credentials.get('reply_subject') or 'Ответ на ваше обращение'),
            body=text,
            from_email=from_email,
            to=[to_email],
            connection=connection,
        )
        sent = message.send()
        return (bool(sent), '') if sent else (False, 'SMTP returned 0 sent')
    except (smtplib.SMTPException, OSError) as exc:  # noqa: BLE001 — граница SMTP
        logger.exception('email send failed to %s', to_email)
        return False, str(exc)[:500]
