from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.test import RequestFactory
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.billing.guards import check_limit
from apps.core.access import require_feature_access, require_roles
from apps.core.tenant import get_request_tenant
from apps.tenants.models import Tenant
from .models import CRMConnection, IntegrationErrorLog, ManagerProfile, WebhookEndpoint
from .services import (
    add_error_log,
    call_adapter_with_reconnect,
    clear_connection_error,
    collect_granted_scopes,
    detect_connection_status,
    extract_scopes_from_callback,
    is_connection_authorized,
    missing_scopes_for_connection,
    refresh_oauth_tokens,
    required_scopes_for,
)
from .tasks import check_crm_connections_health, sync_crm_users
from .webhook_views import _validate_endpoint_auth

integrations_router = Router(tags=['integrations'], auth=JWTAuth())


class ConnectionIn(Schema):
    crm_type: str
    name: str
    credentials: dict
    integration_mode: str = 'webhook'


class ConnectionPatch(Schema):
    name: str | None = None
    credentials: dict | None = None
    is_active: bool | None = None
    integration_mode: str | None = None


class OAuthStartIn(Schema):
    connection_id: int | None = None
    name: str | None = None
    redirect_uri: str | None = None
    install_mode: str | None = None


class WebhookIn(Schema):
    event_type: str
    is_active: bool = True


@integrations_router.get('/connections/')
def list_connections(request):
    require_roles(request, ['owner', 'admin'])
    data = []
    for c in CRMConnection.objects.all().order_by('-id'):
        status = detect_connection_status(c)
        granted_scopes = sorted(collect_granted_scopes(c.credentials or {}))
        required_scopes = sorted(required_scopes_for(c.crm_type))
        default_webhook = c.webhooks.filter(is_active=True).order_by('id').first()
        data.append(
            {
                'id': c.id,
                'crm_type': c.crm_type,
                'name': c.name,
                'integration_mode': c.integration_mode,
                'is_active': c.is_active,
                'is_authorized': is_connection_authorized(c),
                'last_sync_at': c.last_sync_at.isoformat() if c.last_sync_at else None,
                'last_health_check_at': c.last_health_check_at.isoformat() if c.last_health_check_at else None,
                'last_webhook_at': c.last_webhook_at.isoformat() if c.last_webhook_at else None,
                'last_error': c.last_error,
                'webhook_count': c.webhooks.count(),
                'default_webhook_url': _webhook_url(request, default_webhook) if default_webhook else None,
                'status_code': status['code'],
                'status_label': status['label'],
                'status_detail': status['detail'],
                'missing_scopes': status['missing_scopes'],
                'required_scopes': required_scopes,
                'granted_scopes': granted_scopes,
                'error_log_count': c.error_logs.count(),
            }
        )
    return data


@integrations_router.post('/connections/')
def create_connection(request, payload: ConnectionIn):
    require_roles(request, ['owner', 'admin'])
    crm_type = (payload.crm_type or '').lower()
    _require_crm_feature(request, crm_type)
    integration_mode = _normalize_integration_mode(payload.integration_mode)
    tenant = get_request_tenant(request)
    current = CRMConnection.objects.filter(is_active=True).count()
    if not check_limit(tenant, 'max_crm_connections', current):
        return 400, {'detail': 'CRM connections limit reached'}
    c = CRMConnection.objects.create(
        crm_type=crm_type,
        name=payload.name,
        credentials=payload.credentials or {},
        integration_mode=integration_mode,
    )
    _ensure_default_webhook(c)
    _warn_if_scopes_missing(c)
    status = detect_connection_status(c)
    return {
        'id': c.id,
        'status_code': status['code'],
        'status_label': status['label'],
        'missing_scopes': status['missing_scopes'],
    }


@integrations_router.patch('/connections/{connection_id}/')
def update_connection(request, connection_id: int, payload: ConnectionPatch):
    require_roles(request, ['owner', 'admin'])
    c = CRMConnection.objects.filter(id=connection_id).first()
    if not c:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, c)

    updates = payload.dict(exclude_unset=True)
    if 'integration_mode' in updates:
        updates['integration_mode'] = _normalize_integration_mode(updates['integration_mode'])

    for field, value in updates.items():
        setattr(c, field, value)
    c.save()
    _warn_if_scopes_missing(c)
    status = detect_connection_status(c)
    return {
        'detail': 'ok',
        'status_code': status['code'],
        'status_label': status['label'],
        'missing_scopes': status['missing_scopes'],
    }


@integrations_router.delete('/connections/{connection_id}/')
def delete_connection(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    connection.delete()
    return {'detail': 'deleted'}


@integrations_router.post('/connections/{connection_id}/sync-users/')
def sync_users(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    sync_crm_users.delay(tenant.id, connection_id)
    return {'detail': 'sync scheduled'}


@integrations_router.post('/connections/{connection_id}/health-check/')
def health_check_connection(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    result = _run_connection_health_check(connection)
    status = detect_connection_status(connection)
    return {
        **result,
        'status_code': status['code'],
        'status_label': status['label'],
        'status_detail': status['detail'],
    }


@integrations_router.post('/connections/{connection_id}/test/')
def test_connection(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)

    connection_result = _run_connection_health_check(connection)
    endpoint = connection.webhooks.filter(is_active=True).order_by('id').first()
    webhook_result = _run_webhook_auth_probe(connection, endpoint)
    status = detect_connection_status(connection)
    return {
        'connection': connection_result,
        'webhook': webhook_result,
        'status_code': status['code'],
        'status_label': status['label'],
        'status_detail': status['detail'],
    }


@integrations_router.post('/connections/{connection_id}/reconnect/')
def reconnect_connection(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)

    try:
        refreshed = refresh_oauth_tokens(connection)
    except Exception as exc:  # noqa: BLE001
        add_error_log(
            connection,
            code='oauth_reconnect_failed',
            message=f'Автопереавторизация завершилась ошибкой: {exc}',
            resolution='Переавторизуйте подключение вручную через CRM.',
            details={'exception': str(exc)},
        )
        return 400, {'detail': 'OAuth reconnect failed'}
    if not refreshed:
        add_error_log(
            connection,
            code='oauth_reconnect_failed',
            message='Не удалось автоматически обновить OAuth-токен.',
            resolution='Нажмите «Переавторизовать» и подтвердите доступ в CRM.',
        )
        return 400, {'detail': 'OAuth reconnect failed'}

    result = _run_connection_health_check(connection)
    status = detect_connection_status(connection)
    return {
        'detail': 'reconnected',
        **result,
        'status_code': status['code'],
        'status_label': status['label'],
        'status_detail': status['detail'],
    }


@integrations_router.get('/connections/{connection_id}/errors/')
def list_connection_errors(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    rows = IntegrationErrorLog.objects.filter(crm_connection_id=connection_id).order_by('-created_at')[:50]
    return [
        {
            'id': row.id,
            'code': row.code,
            'title': row.title,
            'message': row.message,
            'resolution': row.resolution,
            'level': row.level,
            'details': row.details,
            'created_at': row.created_at.isoformat(),
        }
        for row in rows
    ]


@integrations_router.get('/connections/{connection_id}/managers/')
def list_managers(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    managers = ManagerProfile.objects.filter(crm_connection_id=connection_id).select_related('user')
    return [
        {
            'id': m.id,
            'crm_user_id': m.crm_user_id,
            'crm_user_name': m.crm_user_name,
            'user_id': m.user_id,
            'email': m.user.email if m.user_id else None,
            'is_active': m.is_active,
            'max_active_deals': m.max_active_deals,
        }
        for m in managers
    ]


@integrations_router.get('/connections/{connection_id}/webhooks/')
def list_webhooks(request, connection_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    rows = WebhookEndpoint.objects.filter(crm_connection_id=connection_id).order_by('id')
    return [
        {
            'id': row.id,
            'uuid': str(row.uuid),
            'event_type': row.event_type,
            'is_active': row.is_active,
            'last_received_at': row.last_received_at.isoformat() if row.last_received_at else None,
            'webhook_url': _webhook_url(request, row),
        }
        for row in rows
    ]


@integrations_router.post('/connections/{connection_id}/webhooks/')
def create_webhook(request, connection_id: int, payload: WebhookIn):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    endpoint = WebhookEndpoint.objects.create(
        crm_connection_id=connection_id,
        event_type=payload.event_type,
        secret_token=secrets.token_urlsafe(24),
        is_active=payload.is_active,
    )
    return {
        'id': endpoint.id,
        'uuid': str(endpoint.uuid),
        'secret_token': endpoint.secret_token,
        'webhook_url': _webhook_url(request, endpoint),
    }


@integrations_router.post('/connections/{connection_id}/webhooks/{webhook_id}/rotate-secret/')
def rotate_webhook_secret(request, connection_id: int, webhook_id: int):
    require_roles(request, ['owner', 'admin'])
    connection = CRMConnection.objects.filter(id=connection_id).first()
    if not connection:
        return 404, {'detail': 'Connection not found'}
    _require_connection_feature_access(request, connection)
    endpoint = WebhookEndpoint.objects.filter(id=webhook_id, crm_connection_id=connection_id).first()
    if not endpoint:
        return 404, {'detail': 'Webhook endpoint not found'}
    endpoint.secret_token = secrets.token_urlsafe(24)
    endpoint.save(update_fields=['secret_token'])
    return {'detail': 'ok', 'secret_token': endpoint.secret_token}


@integrations_router.post('/oauth/{crm_type}/start/')
def oauth_start(request, crm_type: str, payload: OAuthStartIn):
    require_roles(request, ['owner', 'admin'])
    install_mode = payload.install_mode or 'oauth'
    return _oauth_start_impl(request, crm_type, payload, install_mode=install_mode)


@integrations_router.post('/marketplace/{crm_type}/install/')
def marketplace_install_start(request, crm_type: str, payload: OAuthStartIn):
    require_roles(request, ['owner', 'admin'])
    return _oauth_start_impl(request, crm_type, payload, install_mode='marketplace')


@integrations_router.get('/oauth/{crm_type}/callback/', auth=None)
def oauth_callback(request, crm_type: str):
    crm_type = crm_type.lower()
    raw_state = request.GET.get('state')
    if not raw_state:
        return 400, {'detail': 'Missing state'}

    try:
        state = signing.loads(raw_state, salt='integration-oauth', max_age=3600)
    except signing.BadSignature:
        return 400, {'detail': 'Invalid state'}

    if state.get('crm_type') != crm_type:
        return 400, {'detail': 'State CRM mismatch'}

    with schema_context('public'):
        tenant = Tenant.objects.filter(id=state.get('tenant_id'), is_active=True).first()
    if not tenant:
        return 404, {'detail': 'Tenant not found'}

    with tenant_context(tenant):
        connection = CRMConnection.objects.filter(id=state.get('connection_id'), crm_type=crm_type).first()
        if not connection:
            return 404, {'detail': 'Connection not found'}

        callback_data = dict(request.GET.items())
        if callback_data.get('error'):
            add_error_log(
                connection,
                code='oauth_reconnect_failed',
                message=f'CRM вернула ошибку OAuth: {callback_data.get("error")}',
                resolution='Повторите установку приложения и подтвердите все запрошенные права.',
                details=callback_data,
            )
            return 400, {'detail': 'OAuth error from CRM', 'error': callback_data.get('error')}

        credentials = dict(connection.credentials or {})
        auth_fields = {key: value for key, value in callback_data.items() if key.startswith('auth[')}
        if auth_fields:
            credentials.update(auth_fields)

        code = request.GET.get('code')
        if code:
            credentials['code'] = code
        access_token = request.GET.get('access_token') or request.GET.get('auth[access_token]')
        if access_token:
            credentials['access_token'] = access_token
        refresh_token = request.GET.get('refresh_token') or request.GET.get('auth[refresh_token]')
        if refresh_token:
            credentials['refresh_token'] = refresh_token
        scopes = extract_scopes_from_callback(callback_data)
        if scopes:
            credentials['scope'] = ' '.join(scopes)
            credentials['granted_scopes'] = scopes

        if crm_type == 'amocrm':
            credentials.setdefault('client_id', settings.AMOCRM_CLIENT_ID)
            credentials.setdefault('client_secret', settings.AMOCRM_CLIENT_SECRET)
            credentials.setdefault('redirect_uri', _default_callback_url(crm_type))
        if crm_type == 'bitrix24':
            credentials.setdefault('client_id', settings.BITRIX24_APP_ID)
            credentials.setdefault('client_secret', settings.BITRIX24_APP_SECRET)

        install_mode = state.get('install_mode')
        if install_mode not in {'oauth', 'marketplace'}:
            install_mode = 'oauth'

        connection.credentials = credentials
        connection.integration_mode = install_mode
        connection.is_active = True
        connection.last_error = ''
        connection.save(update_fields=['credentials', 'integration_mode', 'is_active', 'last_error'])
        _ensure_default_webhook(connection)

        missing_scopes = sorted(missing_scopes_for_connection(connection))
        if missing_scopes:
            add_error_log(
                connection,
                code='scope_missing',
                message=f'Не хватает прав приложения: {", ".join(missing_scopes)}.',
                resolution='Переавторизуйте приложение и подтвердите требуемые scope-права.',
                level='warning',
                details={'missing_scopes': missing_scopes},
                update_connection_error=False,
            )
        else:
            clear_connection_error(connection)

        sync_crm_users.delay(tenant.id, connection.id)
        check_crm_connections_health.delay()

    status = detect_connection_status(connection)
    return {
        'detail': 'OAuth connection saved',
        'tenant_slug': tenant.slug,
        'connection_id': state.get('connection_id'),
        'crm_type': crm_type,
        'status_code': status['code'],
        'status_label': status['label'],
        'missing_scopes': status['missing_scopes'],
    }


def _oauth_start_impl(request, crm_type: str, payload: OAuthStartIn, *, install_mode: str):
    crm_type = crm_type.lower()
    _require_crm_feature(request, crm_type)
    tenant = get_request_tenant(request)
    if crm_type not in {'amocrm', 'bitrix24'}:
        return 400, {'detail': 'Unsupported CRM type'}
    install_mode = _normalize_install_mode(install_mode)

    connection = None
    if payload.connection_id:
        connection = CRMConnection.objects.filter(id=payload.connection_id, crm_type=crm_type).first()
    if not connection:
        current = CRMConnection.objects.filter(is_active=True).count()
        if not check_limit(tenant, 'max_crm_connections', current):
            return 400, {'detail': 'CRM connections limit reached'}
        name = payload.name or f'{crm_type} connection'
        connection = CRMConnection.objects.create(
            crm_type=crm_type,
            name=name,
            credentials={},
            integration_mode=install_mode,
        )
        _ensure_default_webhook(connection)
    else:
        if connection.integration_mode != install_mode:
            connection.integration_mode = install_mode
            connection.save(update_fields=['integration_mode'])

    state = signing.dumps(
        {
            'tenant_id': tenant.id,
            'connection_id': connection.id,
            'crm_type': crm_type,
            'install_mode': install_mode,
        },
        salt='integration-oauth',
    )
    redirect_uri = payload.redirect_uri or _default_callback_url(crm_type)
    authorize_url = _oauth_authorize_url(crm_type, state, redirect_uri, install_mode=install_mode)
    return {
        'connection_id': connection.id,
        'crm_type': crm_type,
        'authorize_url': authorize_url,
        'state': state,
        'redirect_uri': redirect_uri,
        'install_mode': install_mode,
        'required_scopes': sorted(required_scopes_for(crm_type)),
    }


def _run_connection_health_check(connection: CRMConnection) -> dict:
    connection.last_health_check_at = timezone.now()
    try:
        if not is_connection_authorized(connection):
            connection.save(update_fields=['last_health_check_at'])
            return {'ok': False, 'detail': 'Интеграция не авторизована.'}
        call_adapter_with_reconnect(connection, 'list_users')
        clear_connection_error(connection)
        connection.refresh_from_db(fields=['last_error'])
        connection.save(update_fields=['last_health_check_at'])
        return {'ok': True, 'detail': 'CRM API доступен.'}
    except Exception as exc:  # noqa: BLE001
        connection.last_error = str(exc)[:1000]
        connection.save(update_fields=['last_error', 'last_health_check_at'])
        add_error_log(
            connection,
            code='connection_health_failed',
            message=f'Проверка интеграции завершилась ошибкой: {exc}',
            resolution='Проверьте credentials CRM и повторите проверку.',
            details={'exception': str(exc)},
        )
        return {'ok': False, 'detail': str(exc)}


def _run_webhook_auth_probe(connection: CRMConnection, endpoint: WebhookEndpoint | None) -> dict:
    if not endpoint:
        return {'ok': False, 'detail': 'Нет активного webhook endpoint.'}

    payload = {
        'trigger': 'health_probe',
        'secret_token': endpoint.secret_token,
    }
    credentials = connection.credentials or {}
    headers = {'HTTP_X_WEBHOOK_TOKEN': endpoint.secret_token}

    if connection.crm_type == 'bitrix24':
        application_token = credentials.get('application_token')
        if application_token:
            payload['application_token'] = application_token

    body = json.dumps(payload).encode('utf-8')
    if connection.crm_type == 'amocrm':
        signature_secret = credentials.get('webhook_hmac_secret')
        if signature_secret:
            signature = hmac.new(str(signature_secret).encode('utf-8'), body, hashlib.sha256).hexdigest()
            headers['HTTP_X_SIGNATURE'] = signature

    fake_request = RequestFactory().post(
        '/internal/integrations/webhook-probe/',
        data=body,
        content_type='application/json',
        **headers,
    )
    ok = _validate_endpoint_auth(fake_request, endpoint, payload)
    if not ok:
        add_error_log(
            connection,
            code='webhook_auth_failed',
            message='Проверка webhook не пройдена: настройки подписи или токена некорректны.',
            resolution='Сверьте secret token/signature в CRM и нажмите «Проверить» снова.',
            details={'webhook_uuid': str(endpoint.uuid)},
        )
    return {
        'ok': bool(ok),
        'detail': 'Webhook конфигурация валидна.' if ok else 'Webhook конфигурация невалидна.',
        'webhook_url': _webhook_url_for_probe(connection, endpoint),
        'last_received_at': endpoint.last_received_at.isoformat() if endpoint.last_received_at else None,
    }


def _oauth_authorize_url(crm_type: str, state: str, redirect_uri: str, *, install_mode: str) -> str:
    required_scopes = sorted(required_scopes_for(crm_type))
    if crm_type == 'amocrm':
        params = {
            'client_id': settings.AMOCRM_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'state': state,
        }
        if required_scopes:
            params['scope'] = ' '.join(required_scopes)
        base = getattr(settings, 'AMOCRM_MARKETPLACE_INSTALL_URL', '').strip() if install_mode == 'marketplace' else ''
        if not base:
            base = 'https://www.amocrm.ru/oauth'
        return _append_query_params(base, params)

    params = {
        'client_id': settings.BITRIX24_APP_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'state': state,
    }
    if required_scopes:
        params['scope'] = ','.join(required_scopes)
    base = getattr(settings, 'BITRIX24_MARKETPLACE_INSTALL_URL', '').strip() if install_mode == 'marketplace' else ''
    if not base:
        base = 'https://oauth.bitrix.info/oauth/authorize/'
    return _append_query_params(base, params)


def _append_query_params(base_url: str, params: dict[str, str]) -> str:
    sep = '&' if '?' in base_url else '?'
    return f'{base_url}{sep}{urlencode(params)}'


def _default_callback_url(crm_type: str) -> str:
    return f'{settings.PLATFORM_PROTOCOL}://{settings.PLATFORM_DOMAIN}/api/integrations/oauth/{crm_type}/callback/'


def _require_crm_feature(request, crm_type: str):
    if crm_type == 'amocrm':
        feature = 'crm_amocrm'
    elif crm_type == 'bitrix24':
        feature = 'crm_bitrix24'
    else:
        raise HttpError(400, f'Unsupported CRM type: {crm_type}')
    require_feature_access(request, feature)


def _require_connection_feature_access(request, connection: CRMConnection):
    _require_crm_feature(request, connection.crm_type)


def _ensure_default_webhook(connection: CRMConnection):
    WebhookEndpoint.objects.get_or_create(
        crm_connection=connection,
        event_type='default',
        defaults={'secret_token': secrets.token_urlsafe(24), 'is_active': True},
    )


def _webhook_url(request, endpoint: WebhookEndpoint) -> str:
    tenant = get_request_tenant(request)
    return _webhook_url_for_probe(endpoint.crm_connection, endpoint, tenant_slug=tenant.slug)


def _webhook_url_for_probe(connection: CRMConnection, endpoint: WebhookEndpoint, tenant_slug: str | None = None) -> str:
    tenant_slug = tenant_slug or get_request_tenant_slug(connection)
    base = f'{settings.PLATFORM_PROTOCOL}://{settings.PLATFORM_DOMAIN}'
    return f'{base}/wh/{tenant_slug}/{endpoint.uuid}/'


def get_request_tenant_slug(connection: CRMConnection) -> str:
    tenant = get_request_tenant_from_connection(connection)
    return tenant.slug if tenant else 'unknown'


def get_request_tenant_from_connection(connection: CRMConnection):
    # Connection always lives in tenant schema; use current schema tenant first.
    from django.db import connection as db_connection

    tenant = getattr(db_connection, 'tenant', None)
    if tenant and getattr(tenant, 'slug', None):
        return tenant
    with schema_context('public'):
        return Tenant.objects.filter(schema_name=db_connection.schema_name).first()


def _normalize_integration_mode(value: str | None) -> str:
    normalized = (value or 'webhook').strip().lower()
    if normalized not in {'webhook', 'oauth', 'marketplace'}:
        raise HttpError(400, f'Unsupported integration_mode: {value}')
    return normalized


def _normalize_install_mode(value: str | None) -> str:
    normalized = (value or 'oauth').strip().lower()
    if normalized not in {'oauth', 'marketplace'}:
        return 'oauth'
    return normalized

def _warn_if_scopes_missing(connection: CRMConnection):
    missing = sorted(missing_scopes_for_connection(connection))
    if not missing:
        return
    add_error_log(
        connection,
        code='scope_missing',
        message=f'Не хватает прав приложения: {", ".join(missing)}.',
        resolution='Переавторизуйте приложение и подтвердите требуемые scope-права.',
        level='warning',
        details={'missing_scopes': missing},
        update_connection_error=False,
    )
