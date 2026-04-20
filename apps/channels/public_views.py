from __future__ import annotations

import json
import logging

from django.http import JsonResponse
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
        return JsonResponse({'detail': 'Tenant not found'}, status=404)

    with tenant_context(tenant):
        payload = _request_payload(request)
        channel = MessengerChannel.objects.filter(id=channel_id, channel_type=channel_type, is_active=True).first()
        if not channel:
            return JsonResponse({'detail': 'Channel not found'}, status=404)
        if not _validate_webhook_token(request, channel, payload):
            return JsonResponse({'detail': 'Invalid channel token'}, status=403)

    route_incoming_message.delay(tenant.id, channel.id, payload)
    return JsonResponse({'detail': 'ok'})


def _validate_webhook_token(request, channel: MessengerChannel, payload: dict) -> bool:
    credentials = channel.credentials or {}
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
