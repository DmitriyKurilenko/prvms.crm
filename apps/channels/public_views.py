from __future__ import annotations

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from .models import MessengerChannel
from .tasks import route_incoming_message

logger = logging.getLogger(__name__)


def _request_payload(request) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST.dict() if request.POST else {}


@csrf_exempt
@require_POST
def channel_webhook(request, tenant_slug: str, channel_type: str, channel_id: int):
    # Resolve tenant from URL slug
    with schema_context('public'):
        tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
    if not tenant:
        logger.warning('Webhook for unknown tenant: %s', tenant_slug)
        return JsonResponse({'detail': 'Tenant not found'}, status=404)

    with tenant_context(tenant):
        payload = _request_payload(request)
        channel = MessengerChannel.objects.filter(id=channel_id, channel_type=channel_type, is_active=True).first()
        if not channel:
            logger.warning('Webhook for unknown channel: tenant=%s type=%s id=%s', tenant_slug, channel_type, channel_id)
            return JsonResponse({'detail': 'Channel not found'}, status=404)

        # VK confirmation request — special handling before token check
        if channel_type == 'vk' and payload.get('type') == 'confirmation':
            confirmation_code = (channel.credentials or {}).get('confirmation_code', '')
            return HttpResponse(confirmation_code, content_type='text/plain')

        if not _validate_webhook_token(request, channel, payload):
            logger.warning('Invalid webhook token for channel %s', channel.id)
            return JsonResponse({'detail': 'Invalid channel token'}, status=403)

    logger.info('Webhook accepted: tenant=%s channel=%s type=%s', tenant_slug, channel.id, channel_type)
    route_incoming_message.delay(tenant.id, channel.id, payload)
    return JsonResponse({'detail': 'ok'})


def _validate_webhook_token(request, channel: MessengerChannel, payload: dict) -> bool:
    credentials = channel.credentials or {}
    # VK uses 'secret' in payload
    if channel.channel_type == 'vk':
        expected = credentials.get('secret_key')
        if not expected:
            return True
        return payload.get('secret') == expected

    expected = credentials.get('webhook_token')
    if not expected:
        return True
    token = (
        request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        or request.headers.get('X-Max-Bot-Api-Secret')
        or request.headers.get('X-Channel-Token')
        or payload.get('secret_token')
        or request.GET.get('token')
    )
    return token == expected
