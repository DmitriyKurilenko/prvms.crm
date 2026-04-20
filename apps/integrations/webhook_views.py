from __future__ import annotations

import hashlib
import hmac
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_tenants.utils import schema_context, tenant_context

from apps.channels.tasks import route_outgoing_message
from apps.tenants.models import Tenant
from apps.distribution.tasks import process_incoming_webhook
from .services import add_error_log, mark_webhook_received
from .models import WebhookEndpoint


@csrf_exempt
@require_POST
def incoming_crm_webhook(request, tenant_slug: str, webhook_uuid: str):
    with schema_context('public'):
        tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
    if not tenant:
        return JsonResponse({'detail': 'Tenant not found'}, status=404)

    with tenant_context(tenant):
        endpoint = WebhookEndpoint.objects.select_related('crm_connection').filter(uuid=webhook_uuid, is_active=True).first()
        if not endpoint:
            return JsonResponse({'detail': 'Webhook endpoint not found'}, status=404)

        payload = _payload(request)
        if not _validate_endpoint_auth(request, endpoint, payload):
            _register_webhook_failure(endpoint, payload)
            return JsonResponse({'detail': 'Invalid webhook signature/token'}, status=403)

        mark_webhook_received(endpoint.crm_connection, endpoint)

        trigger = str(payload.get('trigger', 'new_lead'))
        if trigger == 'outgoing_message':
            channel_id = int(payload.get('channel_id', 0) or 0)
            chat_session_id = int(payload.get('chat_session_id', 0) or 0)
            if channel_id and chat_session_id:
                route_outgoing_message.delay(tenant.id, channel_id, chat_session_id, payload)
                return JsonResponse({'detail': 'accepted', 'route': 'messenger_outgoing'})
            return JsonResponse({'detail': 'channel_id and chat_session_id are required for outgoing_message'}, status=400)

        process_incoming_webhook.delay(tenant.id, payload.get('trigger', 'new_lead'), payload)
        return JsonResponse({'detail': 'accepted'})


def _payload(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST.dict() if request.POST else {}


def _register_webhook_failure(endpoint: WebhookEndpoint, payload: dict):
    connection = endpoint.crm_connection
    add_error_log(
        connection,
        code='webhook_auth_failed',
        message='Webhook отклонён: неверный токен или подпись запроса.',
        resolution='Проверьте secret token/signature в CRM и повторите отправку webhook.',
        details={
            'webhook_uuid': str(endpoint.uuid),
            'trigger': payload.get('trigger'),
        },
    )


def _validate_endpoint_auth(request, endpoint: WebhookEndpoint, payload: dict) -> bool:
    token = request.headers.get('X-Webhook-Token') or payload.get('secret_token')
    if token != endpoint.secret_token:
        return False

    connection = endpoint.crm_connection
    credentials = connection.credentials or {}
    crm_type = connection.crm_type

    if crm_type == 'bitrix24':
        required = credentials.get('application_token')
        if required:
            incoming = payload.get('auth[application_token]') or payload.get('application_token')
            if incoming != required:
                return False

    if crm_type == 'amocrm':
        signature_secret = credentials.get('webhook_hmac_secret')
        signature = request.headers.get('X-Signature')
        if signature_secret:
            if not signature:
                return False
            digest = hmac.new(
                str(signature_secret).encode('utf-8'),
                request.body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(digest, signature):
                return False

    return True
