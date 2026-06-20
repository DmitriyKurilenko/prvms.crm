from __future__ import annotations

import uuid

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_feature_access, require_roles
from apps.core.tenant import get_request_tenant
from apps.integrations.models import ManagerProfile

from .exolve_client import ExolveError
from .exolve_service import (
    connect_number,
    ensure_sip_accounts,
    get_channel,
    list_available_numbers,
    number_reference,
)
from .models import CallRecord, ExolveSIPAccount

telephony_router = Router(tags=['telephony'], auth=JWTAuth())


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConnectNumberIn(Schema):
    number_code: str
    number: str
    type_id: int | None = None
    region_id: int | None = None


class ClickToCallIn(Schema):
    to_number: str
    deal_id: int | None = None
    contact_id: int | None = None


class ClientLogIn(Schema):
    event: str
    detail: str = ''


# ---------------------------------------------------------------------------
# Канал и номер
# ---------------------------------------------------------------------------

@telephony_router.get('/channel/')
def channel_info(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    channel = get_channel()
    return {
        'exolve_number': channel.exolve_number,
        'number_code': channel.number_code,
        'status': channel.status,
        'status_detail': channel.status_detail,
        'is_active': channel.is_active,
    }


@telephony_router.get('/number-reference/')
def number_reference_view(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    try:
        return number_reference()
    except ExolveError as exc:
        raise HttpError(502, f'Exolve: {exc}') from exc


@telephony_router.get('/available-numbers/')
def available_numbers(request, type_id: int = 1104, region_id: int | None = None, mask: str = '', limit: int = 20):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    try:
        return list_available_numbers(type_id=type_id, region_id=region_id, mask=mask, limit=limit)
    except ExolveError as exc:
        raise HttpError(502, f'Exolve: {exc}') from exc


@telephony_router.post('/connect-number/')
def connect_number_view(request, payload: ConnectNumberIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    tenant = get_request_tenant(request)
    try:
        channel = connect_number(
            tenant,
            number_code=payload.number_code,
            number_e164=payload.number,
            type_id=payload.type_id,
            region_id=payload.region_id,
        )
    except ExolveError as exc:
        raise HttpError(502, f'Exolve: {exc}') from exc
    return {'status': channel.status, 'exolve_number': channel.exolve_number, 'detail': channel.status_detail}


# ---------------------------------------------------------------------------
# SIP-аккаунты менеджеров
# ---------------------------------------------------------------------------

@telephony_router.get('/sip-accounts/')
def sip_accounts(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    return [
        {
            'id': a.id,
            'manager_id': a.manager_id,
            'manager_name': a.manager.crm_user_name,
            'username': a.username,
            'display_number': a.display_number,
            'status': a.status,
            'status_detail': a.status_detail,
            'is_active': a.is_active,
        }
        for a in ExolveSIPAccount.objects.select_related('manager').order_by('manager__crm_user_name')
    ]


@telephony_router.post('/sip-accounts/provision/')
def provision_sip(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    tenant = get_request_tenant(request)
    try:
        count = ensure_sip_accounts(tenant)
    except ExolveError as exc:
        raise HttpError(502, f'Exolve: {exc}') from exc
    return {'provisioned': count}


# ---------------------------------------------------------------------------
# WebRTC-креды текущего менеджера (для Web Voice SDK)
# ---------------------------------------------------------------------------

@telephony_router.get('/webrtc-credentials/')
def webrtc_credentials(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    account = (
        ExolveSIPAccount.objects
        .filter(manager__user_id=request.auth.id, is_active=True, status='active')
        .select_related('manager')
        .first()
    )
    channel = get_channel()
    return {
        'sip_domain': settings.EXOLVE_SIP_DOMAIN,
        'wss_url': getattr(settings, 'EXOLVE_WSS_URL', '') or None,
        'username': account.username if account else None,
        'password': account.password if account else None,
        'display_number': account.display_number if account else channel.exolve_number,
        'manager_id': account.manager_id if account else None,
        'ready': bool(account and account.username and account.password),
    }


# ---------------------------------------------------------------------------
# Click-to-call (журналирование исходящего, набор идёт в браузере через SDK)
# ---------------------------------------------------------------------------

@telephony_router.post('/click-to-call/')
def click_to_call(request, payload: ClickToCallIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    manager = ManagerProfile.objects.filter(user_id=request.auth.id, is_active=True).first()
    channel = get_channel()
    record = CallRecord.objects.create(
        call_sid=f'cti-{uuid.uuid4()}',
        direction='outbound',
        caller_number=channel.exolve_number,
        called_number=payload.to_number,
        result='answered',
        manager=manager,
        crm_contact_id=str(payload.contact_id or ''),
        crm_lead_id=str(payload.deal_id or ''),
        started_at=timezone.now(),
    )
    return {'call_id': record.id, 'to_number': payload.to_number}


@telephony_router.post('/client-log/')
def client_log(request, payload: ClientLogIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    import logging
    logging.getLogger('apps.telephony.client').warning(
        'PHONE-CLIENT user=%s event=%s detail=%s', request.auth.id, payload.event, payload.detail[:600],
    )
    return {'ok': True}


# ---------------------------------------------------------------------------
# Журнал звонков
# ---------------------------------------------------------------------------

@telephony_router.get('/calls/')
def list_calls(request, result: str = None, direction: str = None, date_from: str = None, date_to: str = None):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    qs = CallRecord.objects.select_related('manager').order_by('-started_at')
    if result:
        qs = qs.filter(result=result)
    if direction:
        qs = qs.filter(direction=direction)
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)
    return [
        {
            'id': c.id,
            'call_sid': c.call_sid,
            'direction': c.direction,
            'caller_number': c.caller_number,
            'called_number': c.called_number,
            'result': c.result,
            'duration': c.duration,
            'talk_time': c.talk_time,
            'manager_id': c.manager_id,
            'manager_name': c.manager.crm_user_name if c.manager_id else None,
            'crm_contact_id': c.crm_contact_id,
            'crm_lead_id': c.crm_lead_id,
            'started_at': c.started_at.isoformat(),
            'record_file': c.record_file.url if c.record_file else None,
        }
        for c in qs[:300]
    ]


@telephony_router.get('/calls/{call_id}/record/')
def call_record_file(request, call_id: int):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    c = CallRecord.objects.get(id=call_id)
    if not c.record_file:
        raise HttpError(404, 'Record not found')
    return FileResponse(c.record_file.open('rb'))


@telephony_router.get('/stats/')
def call_stats(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    calls = CallRecord.objects.all()
    total = calls.count()
    missed = calls.filter(result='missed').count()
    answered = calls.filter(result='answered').count()
    return {'total': total, 'missed': missed, 'answered': answered}
