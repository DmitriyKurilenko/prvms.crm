"""Публичные webhook-эндпоинты телефонии Exolve (без аутентификации JWT).

- ``/telephony/exolve/ipcr/``   — JSON-RPC getControlCallFollowMe: синхронное
  решение по входящему звонку (резолв тенанта, дедуп сделки, маршрут).
- ``/telephony/exolve/events/`` — Call Events (b/o/s/h/d/e/crr): журнал и записи.

Доступ ограничивается секретом ``EXOLVE_WEBHOOK_SECRET`` в query (?key=…),
который зашивается в URL при регистрации переадресации/событий.
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_tenants.utils import tenant_context

from .exolve_service import build_followme_response, resolve_tenant_by_number
from .tasks import process_exolve_event

logger = logging.getLogger(__name__)


def _payload(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _secret_ok(request) -> bool:
    secret = (getattr(settings, 'EXOLVE_WEBHOOK_SECRET', '') or '').strip()
    if not secret:
        return True
    return request.GET.get('key') == secret


def _empty_followme(rpc_id, sip_id: str) -> dict:
    return {
        'id': rpc_id,
        'jsonrpc': '2.0',
        'sip_id': sip_id,
        'result': {'redirect_type': 1, 'followme_struct': [1, []]},
    }


@csrf_exempt
@require_POST
def exolve_ipcr(request):
    if not _secret_ok(request):
        return JsonResponse({'error': 'forbidden'}, status=403)

    data = _payload(request)
    rpc_id = data.get('id', '1')
    params = data.get('params', {}) or {}
    sip_id = str(params.get('sip_id', ''))
    numberA = str(params.get('numberA', ''))
    call_sid = str(params.get('call_sid', ''))
    logger.info('Exolve IPCR request sip_id=%s numberA=%s call_sid=%s', sip_id, numberA, call_sid)

    tenant = resolve_tenant_by_number(sip_id)
    if not tenant:
        logger.warning('Exolve IPCR: тенант не найден для номера %s', sip_id)
        return JsonResponse(_empty_followme(rpc_id, sip_id))

    try:
        with tenant_context(tenant):
            response = build_followme_response(rpc_id, tenant, sip_id, numberA, call_sid)
        return JsonResponse(response)
    except Exception:
        logger.exception('Exolve IPCR: ошибка решения по звонку call_sid=%s', call_sid)
        # Звонок не теряем: возвращаем пустой маршрут, Exolve уйдёт на reserve.
        return JsonResponse(_empty_followme(rpc_id, sip_id))


@csrf_exempt
@require_POST
def exolve_events(request):
    if not _secret_ok(request):
        return JsonResponse({'error': 'forbidden'}, status=403)

    data = _payload(request)
    called = str(data.get('to') or data.get('called_number') or '')
    tenant = resolve_tenant_by_number(called)
    if not tenant:
        # Для типа 'e' поле 'to' может отсутствовать — пробуем 'from' маловероятно;
        # без номера тенанта событие игнорируем, но фиксируем в лог.
        logger.info('Exolve event без резолва тенанта: type=%s to=%s', data.get('type'), called)
        return JsonResponse({'detail': 'ignored'})

    process_exolve_event.delay(tenant.id, data)
    return JsonResponse({'detail': 'accepted'})
