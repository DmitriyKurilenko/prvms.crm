"""Shared router, schemas and helpers for the split `apps.integrations.api`.

`integrations_router` is defined here once; the domain modules
(`connections_api`, `webhooks_api`, `oauth_api`) import it and attach
their endpoints via decorators. The thin `apps.integrations.api` shim
imports every domain module for that side-effect and re-exports
`integrations_router` for `config/api.py`.

These helpers stay in the API layer (not `services.py`) because they are
request/URL-coupled: they take the HTTP `request`, build absolute webhook
URLs from settings, and raise `HttpError`. `services.py` remains
request-agnostic domain logic.
"""
from __future__ import annotations

import secrets

from django.conf import settings
from django_tenants.utils import schema_context
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_feature_access
from apps.core.tenant import get_request_tenant
from apps.tenants.models import Tenant

from .models import CRMConnection, WebhookEndpoint
from .services import add_error_log, missing_scopes_for_connection

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


def _default_callback_url(crm_type: str) -> str:
    return f'{settings.PLATFORM_PROTOCOL}://{settings.PLATFORM_DOMAIN}/api/integrations/oauth/{crm_type}/callback/'


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
