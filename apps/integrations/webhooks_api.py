from __future__ import annotations

import secrets

from apps.core.access import require_roles

from ._api_common import (
    WebhookIn,
    _require_connection_feature_access,
    _webhook_url,
    integrations_router,
)
from .models import CRMConnection, WebhookEndpoint


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
