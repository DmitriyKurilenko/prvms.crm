from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django_tenants.utils import schema_context, tenant_context

from apps.billing.guards import check_limit
from apps.core.access import require_roles
from apps.core.tenant import get_request_tenant
from apps.tenants.models import Tenant

from ._api_common import (
    OAuthStartIn,
    _default_callback_url,
    _ensure_default_webhook,
    _normalize_install_mode,
    _require_crm_feature,
    integrations_router,
)
from .models import CRMConnection
from .services import (
    add_error_log,
    clear_connection_error,
    detect_connection_status,
    extract_scopes_from_callback,
    missing_scopes_for_connection,
    required_scopes_for,
)
from .tasks import check_crm_connections_health, sync_crm_users


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
