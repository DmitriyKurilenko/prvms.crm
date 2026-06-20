from __future__ import annotations

from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from .adapters import get_adapter
from .models import CRMConnection, IntegrationErrorLog, WebhookEndpoint

STATUS_LABELS = {
    'working': 'Работает',
    'requires_authorization': 'Требуется авторизация',
    'webhook_error': 'Ошибка webhook',
    'insufficient_scope': 'Недостаточно прав',
    'error': 'Ошибка подключения',
    'disabled': 'Отключено',
}

REQUIRED_SCOPES = {
    'amocrm': {'crm', 'users'},
    'bitrix24': {'crm', 'user'},
}


def required_scopes_for(crm_type: str) -> set[str]:
    return set(REQUIRED_SCOPES.get((crm_type or '').lower(), set()))


def parse_scopes(raw: Any) -> set[str]:
    if isinstance(raw, str):
        return {item.strip().lower() for item in raw.replace(',', ' ').split() if item.strip()}
    if isinstance(raw, (list, tuple, set)):
        scopes: set[str] = set()
        for item in raw:
            scopes.update(parse_scopes(item))
        return scopes
    return set()


def collect_granted_scopes(credentials: dict | None) -> set[str]:
    credentials = credentials or {}
    candidates = [
        credentials.get('scope'),
        credentials.get('scopes'),
        credentials.get('auth[scope]'),
        credentials.get('auth[scopes]'),
        credentials.get('granted_scopes'),
    ]
    scopes: set[str] = set()
    for item in candidates:
        scopes.update(parse_scopes(item))
    return scopes


def missing_scopes_for_connection(connection: CRMConnection) -> set[str]:
    if connection.integration_mode not in {'oauth', 'marketplace'}:
        return set()
    required = required_scopes_for(connection.crm_type)
    if not required:
        return set()
    granted = collect_granted_scopes(connection.credentials or {})
    return required - granted


def is_connection_authorized(connection: CRMConnection) -> bool:
    credentials = connection.credentials or {}
    crm_type = (connection.crm_type or '').lower()
    if crm_type == 'amocrm':
        has_location = bool(str(credentials.get('base_url', '')).strip() or str(credentials.get('subdomain', '')).strip())
        return has_location and bool(str(credentials.get('access_token', '')).strip())
    if crm_type == 'bitrix24':
        has_webhook_url = bool(str(credentials.get('webhook_url', '')).strip())
        has_oauth = bool(str(credentials.get('base_url', '')).strip() and str(credentials.get('access_token', '')).strip())
        return has_webhook_url or has_oauth
    return False


def detect_connection_status(connection: CRMConnection) -> dict[str, Any]:
    if not connection.is_active:
        return {'code': 'disabled', 'label': STATUS_LABELS['disabled'], 'detail': 'Подключение отключено.', 'missing_scopes': []}

    if not is_connection_authorized(connection):
        return {
            'code': 'requires_authorization',
            'label': STATUS_LABELS['requires_authorization'],
            'detail': 'Не хватает OAuth/webhook credentials для доступа к CRM.',
            'missing_scopes': [],
        }

    missing_scopes = sorted(missing_scopes_for_connection(connection))
    if missing_scopes:
        return {
            'code': 'insufficient_scope',
            'label': STATUS_LABELS['insufficient_scope'],
            'detail': f'Нужно выдать права: {", ".join(missing_scopes)}.',
            'missing_scopes': missing_scopes,
        }

    message = (connection.last_error or '').strip()
    message_lower = message.lower()
    if message:
        if 'webhook' in message_lower:
            return {
                'code': 'webhook_error',
                'label': STATUS_LABELS['webhook_error'],
                'detail': message,
                'missing_scopes': [],
            }
        return {
            'code': 'error',
            'label': STATUS_LABELS['error'],
            'detail': message,
            'missing_scopes': [],
        }

    return {'code': 'working', 'label': STATUS_LABELS['working'], 'detail': 'Интеграция активна.', 'missing_scopes': []}


def add_error_log(
    connection: CRMConnection,
    code: str,
    message: str,
    *,
    title: str = '',
    resolution: str = '',
    level: str = 'error',
    details: dict | None = None,
    update_connection_error: bool = True,
) -> IntegrationErrorLog:
    entry = IntegrationErrorLog.objects.create(
        crm_connection=connection,
        code=code,
        title=title or _default_title_for_code(code),
        message=message,
        resolution=resolution or _default_resolution_for_code(code),
        level=level,
        details=details or {},
    )
    if update_connection_error and level == 'error':
        connection.last_error = message[:1000]
        connection.save(update_fields=['last_error'])
    return entry


def clear_connection_error(connection: CRMConnection):
    if connection.last_error:
        connection.last_error = ''
        connection.save(update_fields=['last_error'])


def mark_webhook_received(connection: CRMConnection, endpoint: WebhookEndpoint):
    now = timezone.now()
    endpoint.last_received_at = now
    endpoint.save(update_fields=['last_received_at'])
    connection.last_webhook_at = now
    if 'webhook' in (connection.last_error or '').lower():
        connection.last_error = ''
        connection.save(update_fields=['last_webhook_at', 'last_error'])
    else:
        connection.save(update_fields=['last_webhook_at'])


def extract_scopes_from_callback(callback_data: dict[str, Any]) -> list[str]:
    scopes = parse_scopes(
        callback_data.get('scope')
        or callback_data.get('scopes')
        or callback_data.get('auth[scope]')
        or callback_data.get('auth[scopes]')
    )
    return sorted(scopes)


def call_adapter_with_reconnect(connection: CRMConnection, method_name: str, *args, **kwargs):
    adapter = get_adapter(connection)
    method = getattr(adapter, method_name)
    try:
        return method(*args, **kwargs)
    except requests.HTTPError as exc:
        if _is_auth_http_error(exc) and refresh_oauth_tokens(connection):
            adapter = get_adapter(connection)
            method = getattr(adapter, method_name)
            return method(*args, **kwargs)
        raise


def refresh_oauth_tokens(connection: CRMConnection) -> bool:
    credentials = dict(connection.credentials or {})
    crm_type = (connection.crm_type or '').lower()
    if crm_type == 'amocrm':
        return _refresh_amocrm_tokens(connection, credentials)
    if crm_type == 'bitrix24':
        return _refresh_bitrix_tokens(connection, credentials)
    return False


def _refresh_amocrm_tokens(connection: CRMConnection, credentials: dict) -> bool:
    refresh_token = str(credentials.get('refresh_token', '')).strip()
    client_id = str(credentials.get('client_id') or settings.AMOCRM_CLIENT_ID or '').strip()
    client_secret = str(credentials.get('client_secret') or settings.AMOCRM_CLIENT_SECRET or '').strip()
    redirect_uri = str(credentials.get('redirect_uri') or settings.AMOCRM_REDIRECT_URI or '').strip()
    base_url = str(credentials.get('base_url', '')).strip().rstrip('/')
    subdomain = str(credentials.get('subdomain', '')).strip()
    if not base_url and subdomain:
        base_url = f'https://{subdomain}.amocrm.ru'
    if not (refresh_token and client_id and client_secret and redirect_uri and base_url):
        return False

    response = requests.post(
        f'{base_url}/oauth2/access_token',
        json={
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'redirect_uri': redirect_uri,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json() if response.text else {}
    new_access = str(payload.get('access_token', '')).strip()
    if not new_access:
        return False
    credentials['access_token'] = new_access
    new_refresh = str(payload.get('refresh_token', '')).strip()
    if new_refresh:
        credentials['refresh_token'] = new_refresh
    expires_in = int(payload.get('expires_in') or 0)
    if expires_in > 0:
        credentials['token_expires_at'] = (timezone.now() + timedelta(seconds=expires_in)).isoformat()
    scope_value = payload.get('scope')
    if scope_value:
        credentials['scope'] = scope_value
        credentials['granted_scopes'] = sorted(parse_scopes(scope_value))
    connection.credentials = credentials
    connection.is_active = True
    connection.last_error = ''
    connection.save(update_fields=['credentials', 'is_active', 'last_error'])
    add_error_log(
        connection,
        'oauth_reconnected',
        'OAuth токен amoCRM автоматически обновлён.',
        title='Токен обновлён',
        resolution='Никаких действий не требуется.',
        level='info',
        update_connection_error=False,
    )
    return True


def _refresh_bitrix_tokens(connection: CRMConnection, credentials: dict) -> bool:
    refresh_token = str(credentials.get('refresh_token', '')).strip()
    client_id = str(credentials.get('client_id') or settings.BITRIX24_APP_ID or '').strip()
    client_secret = str(credentials.get('client_secret') or settings.BITRIX24_APP_SECRET or '').strip()
    if not (refresh_token and client_id and client_secret):
        return False

    response = requests.post(
        'https://oauth.bitrix.info/oauth/token/',
        data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json() if response.text else {}
    new_access = str(payload.get('access_token', '')).strip()
    if not new_access:
        return False
    credentials['access_token'] = new_access
    new_refresh = str(payload.get('refresh_token', '')).strip()
    if new_refresh:
        credentials['refresh_token'] = new_refresh
    if payload.get('domain'):
        credentials['base_url'] = f"https://{payload['domain']}"
    scope_value = payload.get('scope')
    if scope_value:
        credentials['scope'] = scope_value
        credentials['granted_scopes'] = sorted(parse_scopes(scope_value))
    connection.credentials = credentials
    connection.is_active = True
    connection.last_error = ''
    connection.save(update_fields=['credentials', 'is_active', 'last_error'])
    add_error_log(
        connection,
        'oauth_reconnected',
        'OAuth токен Битрикс24 автоматически обновлён.',
        title='Токен обновлён',
        resolution='Никаких действий не требуется.',
        level='info',
        update_connection_error=False,
    )
    return True


def _is_auth_http_error(exc: requests.HTTPError) -> bool:
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    return status in {401, 403}


def _default_title_for_code(code: str) -> str:
    mapping = {
        'webhook_auth_failed': 'Webhook отклонён',
        'scope_missing': 'Недостаточно прав интеграции',
        'oauth_reconnect_failed': 'Не удалось обновить OAuth',
        'connection_health_failed': 'Проверка интеграции не пройдена',
        'manager_sync_failed': 'Синхронизация менеджеров не выполнена',
    }
    return mapping.get(code, 'Проблема интеграции')


def _default_resolution_for_code(code: str) -> str:
    mapping = {
        'webhook_auth_failed': 'Проверьте секрет webhook и подпись в CRM, затем повторите отправку события.',
        'scope_missing': 'Откройте переавторизацию и подтвердите все требуемые права приложения.',
        'oauth_reconnect_failed': 'Нажмите «Переавторизовать» и подтвердите доступ в CRM.',
        'connection_health_failed': 'Проверьте credentials и доступность CRM API, затем нажмите «Проверить».',
        'manager_sync_failed': 'Проверьте права на чтение пользователей в CRM и повторите синхронизацию.',
    }
    return mapping.get(code, 'Откройте карточку интеграции и запустите повторную проверку.')
