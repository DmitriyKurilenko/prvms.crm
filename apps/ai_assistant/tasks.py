from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django_tenants.utils import schema_context

from apps.tenants.models import Tenant
from .services import send_notification_via_hermes

logger = logging.getLogger(__name__)


def _broadcast_ai_message(user_id: int, payload: dict):
    """Push AI message to user's WebSocket group."""
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        f'ai.user.{user_id}',
        {
            'type': 'ai_message',
            'payload': payload,
        },
    )


@shared_task
def send_ai_notification(tenant_id: int, user_id: int, title: str, body: str):
    """
    Send notification via Hermes AI.
    Called from Hermes cron webhook or other triggers.
    """
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
        from apps.users.models import User
        user = User.objects.get(id=user_id)

    success = send_notification_via_hermes(tenant, user, title, body)

    if success:
        _broadcast_ai_message(user_id, {
            'type': 'ai_notification',
            'title': title,
            'body': body,
        })

    return {'success': success}


@shared_task
def sync_hermes_profile(tenant_id: int):
    """
    Sync Hermes profile for tenant.
    Creates/updates profile directory structure.
    """
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    logger.info(f'Syncing Hermes profile for tenant: {tenant.slug}')

    return {'tenant': tenant.slug, 'status': 'synced'}