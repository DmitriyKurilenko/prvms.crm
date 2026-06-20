from __future__ import annotations

import hashlib
import hmac
import json

from django.test import RequestFactory
from django.utils import timezone

from apps.billing.guards import check_limit
from apps.core.access import require_roles
from apps.core.tenant import get_request_tenant

from ._api_common import (
    ConnectionIn,
    ConnectionPatch,
    _ensure_default_webhook,
    _normalize_integration_mode,
    _require_connection_feature_access,
    _require_crm_feature,
    _warn_if_scopes_missing,
    _webhook_url,
    _webhook_url_for_probe,
    integrations_router,
)
from .models import CRMConnection, IntegrationErrorLog, ManagerProfile, WebhookEndpoint
from .services import (
    add_error_log,
    call_adapter_with_reconnect,
    clear_connection_error,
    collect_granted_scopes,
    detect_connection_status,
    is_connection_authorized,
    refresh_oauth_tokens,
    required_scopes_for,
)
from .tasks import sync_crm_users
from .webhook_views import _validate_endpoint_auth


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
