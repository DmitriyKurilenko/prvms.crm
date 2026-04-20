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
from .models import CallQueue, CallRecord, IVRMenu, PhoneExtension, SIPTrunk
from .tasks import sync_freeswitch_config, esl_originate, _check_gateway_status

telephony_router = Router(tags=['telephony'], auth=JWTAuth())


class TrunkIn(Schema):
    name: str
    trunk_type: str
    crm_connection_id: int | None = None
    credentials: dict = {}
    inbound_numbers: list[str] = []
    is_active: bool = True


class TrunkPatchIn(Schema):
    name: str | None = None
    trunk_type: str | None = None
    crm_connection_id: int | None = None
    credentials: dict | None = None
    inbound_numbers: list[str] | None = None
    is_active: bool | None = None


class ExtensionIn(Schema):
    manager_id: int
    extension: str
    sip_password: str
    webrtc_enabled: bool = True
    voicemail_enabled: bool = False
    is_active: bool = True


class ExtensionPatchIn(Schema):
    manager_id: int | None = None
    extension: str | None = None
    sip_password: str | None = None
    webrtc_enabled: bool | None = None
    voicemail_enabled: bool | None = None
    is_active: bool | None = None


class IvrIn(Schema):
    name: str
    greeting_tts: str = ''
    options: list[dict] = []
    timeout: int = 10
    is_active: bool = True


class IvrPatchIn(Schema):
    name: str | None = None
    greeting_tts: str | None = None
    options: list[dict] | None = None
    timeout: int | None = None
    is_active: bool | None = None


class QueueIn(Schema):
    name: str
    strategy: str = 'ring_all'
    members: list[int] = []
    ring_timeout: int = 20
    max_wait_time: int = 120
    announce_position: bool = True
    is_active: bool = True


class QueuePatchIn(Schema):
    name: str | None = None
    strategy: str | None = None
    members: list[int] | None = None
    ring_timeout: int | None = None
    max_wait_time: int | None = None
    announce_position: bool | None = None
    is_active: bool | None = None


@telephony_router.get('/trunks/')
def list_trunks(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    return [
        {'id': t.id, 'name': t.name, 'trunk_type': t.trunk_type, 'status': t.status, 'status_detail': t.status_detail, 'is_active': t.is_active}
        for t in SIPTrunk.objects.all().order_by('-id')
    ]


def _normalize_trunk_credentials(trunk_type: str, creds: dict) -> dict:
    if trunk_type == 'exolve' and not creds.get('proxy'):
        creds['proxy'] = 'sip.exolve.ru'
    return creds


@telephony_router.post('/trunks/')
def create_trunk(request, payload: TrunkIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    tenant = get_request_tenant(request)
    data = payload.dict()
    data['credentials'] = _normalize_trunk_credentials(data['trunk_type'], data.get('credentials', {}))
    t = SIPTrunk.objects.create(**data)
    sync_freeswitch_config.delay(tenant.id, t.id)
    return {'id': t.id}


@telephony_router.patch('/trunks/{trunk_id}/')
def patch_trunk(request, trunk_id: int, payload: TrunkPatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    tenant = get_request_tenant(request)
    data = payload.dict(exclude_unset=True)
    if 'credentials' in data or 'trunk_type' in data:
        trunk = SIPTrunk.objects.filter(id=trunk_id).first()
        if trunk:
            trunk_type = data.get('trunk_type', trunk.trunk_type)
            creds = data.get('credentials', trunk.credentials or {})
            data['credentials'] = _normalize_trunk_credentials(trunk_type, creds)
    SIPTrunk.objects.filter(id=trunk_id).update(**data)
    sync_freeswitch_config.delay(tenant.id, trunk_id)
    return {'detail': 'ok'}


@telephony_router.delete('/trunks/{trunk_id}/')
def delete_trunk(request, trunk_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    SIPTrunk.objects.filter(id=trunk_id).delete()
    return {'detail': 'deleted'}


@telephony_router.post('/trunks/{trunk_id}/test/')
def test_trunk(request, trunk_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    trunk = SIPTrunk.objects.filter(id=trunk_id).first()
    if not trunk:
        raise HttpError(404, 'Trunk not found')
    try:
        is_reg, detail = _check_gateway_status(trunk.name)
        SIPTrunk.objects.filter(id=trunk_id).update(
            status='active' if is_reg else 'error',
            status_detail=detail,
            last_registration_at=timezone.now() if is_reg else None,
        )
        return {'detail': detail, 'status': 'active' if is_reg else 'error'}
    except Exception:
        SIPTrunk.objects.filter(id=trunk_id).update(status='error', status_detail='ESL недоступен')
        raise HttpError(502, 'Cannot reach FreeSWITCH ESL')


@telephony_router.get('/extensions/')
def list_extensions(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    return [
        {
            'id': e.id,
            'manager_id': e.manager_id,
            'extension': e.extension,
            'webrtc_enabled': e.webrtc_enabled,
            'voicemail_enabled': e.voicemail_enabled,
            'is_active': e.is_active,
        }
        for e in PhoneExtension.objects.all().order_by('extension')
    ]


@telephony_router.post('/extensions/')
def create_extension(request, payload: ExtensionIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    e = PhoneExtension.objects.create(**payload.dict())
    return {'id': e.id}


@telephony_router.patch('/extensions/{extension_id}/')
def patch_extension(request, extension_id: int, payload: ExtensionPatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    PhoneExtension.objects.filter(id=extension_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@telephony_router.delete('/extensions/{extension_id}/')
def delete_extension(request, extension_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    PhoneExtension.objects.filter(id=extension_id).delete()
    return {'detail': 'deleted'}


@telephony_router.get('/ivr/')
def list_ivr(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    return [{'id': ivr.id, 'name': ivr.name, 'options': ivr.options, 'timeout': ivr.timeout, 'is_active': ivr.is_active} for ivr in IVRMenu.objects.all().order_by('-id')]


@telephony_router.post('/ivr/')
def create_ivr(request, payload: IvrIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    ivr = IVRMenu.objects.create(**payload.dict())
    return {'id': ivr.id}


@telephony_router.patch('/ivr/{ivr_id}/')
def patch_ivr(request, ivr_id: int, payload: IvrPatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    IVRMenu.objects.filter(id=ivr_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@telephony_router.delete('/ivr/{ivr_id}/')
def delete_ivr(request, ivr_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    IVRMenu.objects.filter(id=ivr_id).delete()
    return {'detail': 'deleted'}


@telephony_router.get('/queues/')
def list_queues(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    return [
        {
            'id': q.id,
            'name': q.name,
            'strategy': q.strategy,
            'members': list(q.members.values_list('id', flat=True)),
            'ring_timeout': q.ring_timeout,
            'max_wait_time': q.max_wait_time,
            'announce_position': q.announce_position,
            'is_active': q.is_active,
        }
        for q in CallQueue.objects.all().order_by('-id')
    ]


@telephony_router.post('/queues/')
def create_queue(request, payload: QueueIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    q = CallQueue.objects.create(
        name=payload.name,
        strategy=payload.strategy,
        ring_timeout=payload.ring_timeout,
        max_wait_time=payload.max_wait_time,
        announce_position=payload.announce_position,
        is_active=payload.is_active,
    )
    if payload.members:
        q.members.set(payload.members)
    return {'id': q.id}


@telephony_router.patch('/queues/{queue_id}/')
def patch_queue(request, queue_id: int, payload: QueuePatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    q = CallQueue.objects.get(id=queue_id)
    data = payload.dict(exclude_unset=True)
    members = data.pop('members', None)
    for key, value in data.items():
        setattr(q, key, value)
    q.save()
    if members is not None:
        q.members.set(members)
    return {'detail': 'ok'}


@telephony_router.delete('/queues/{queue_id}/')
def delete_queue(request, queue_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'telephony')
    CallQueue.objects.filter(id=queue_id).delete()
    return {'detail': 'deleted'}


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
            'uuid': c.freeswitch_uuid,
            'direction': c.direction,
            'caller_number': c.caller_number,
            'called_number': c.called_number,
            'result': c.result,
            'duration': c.duration,
            'manager_id': c.manager_id,
            'manager_name': c.manager.crm_user_name if c.manager_id else None,
            'started_at': c.started_at.isoformat(),
            'record_file': c.record_file.url if c.record_file else None,
        }
        for c in qs[:300]
    ]


@telephony_router.get('/calls/{call_id}/')
def call_detail(request, call_id: int):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    c = CallRecord.objects.get(id=call_id)
    return {
        'id': c.id,
        'uuid': c.freeswitch_uuid,
        'direction': c.direction,
        'caller_number': c.caller_number,
        'called_number': c.called_number,
        'result': c.result,
        'duration': c.duration,
        'wait_time': c.wait_time,
        'record_file': c.record_file.url if c.record_file else None,
        'started_at': c.started_at.isoformat(),
        'answered_at': c.answered_at.isoformat() if c.answered_at else None,
        'ended_at': c.ended_at.isoformat() if c.ended_at else None,
    }


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
    avg_duration = sum(c.duration for c in calls[:500]) / total if total else 0
    return {'total': total, 'missed': missed, 'avg_duration': avg_duration}


@telephony_router.post('/call/originate')
def originate(request, payload: dict):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')

    from_number = str(payload.get('from_number', payload.get('caller_number', '')))
    to_number = str(payload.get('to_number', payload.get('called_number', '')))
    trunk_id = payload.get('trunk_id')

    trunk = None
    trunk_name = None
    if trunk_id:
        trunk = SIPTrunk.objects.filter(id=trunk_id, is_active=True).first()
        if trunk:
            trunk_name = trunk.name

    try:
        call_uuid = esl_originate(
            caller=from_number,
            destination=to_number,
            trunk_name=trunk_name,
            variables={'origination_caller_id_number': from_number},
        )
    except Exception:
        raise HttpError(502, 'Failed to connect to telephony server')

    call = CallRecord.objects.create(
        sip_trunk=trunk,
        freeswitch_uuid=call_uuid,
        direction='outbound',
        caller_number=from_number,
        called_number=to_number,
        result='answered',
        duration=0,
        wait_time=0,
        manager_id=payload.get('manager_id'),
        started_at=timezone.now(),
    )
    return {'detail': 'originate sent', 'call_id': call.id, 'uuid': call_uuid}


@telephony_router.get('/webrtc/credentials')
def webrtc_credentials(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'telephony')
    tenant = get_request_tenant(request)
    extension = PhoneExtension.objects.filter(manager__user_id=request.auth.id, is_active=True).select_related('manager').first()
    return {
        'wss_url': settings.FREESWITCH_WSS_URL,
        'esl_host': settings.FREESWITCH_ESL_HOST,
        'extension': extension.extension if extension else None,
        'sip_password': extension.sip_password if extension else None,
        'manager_id': extension.manager_id if extension else None,
        'sip_domain': getattr(tenant, 'sip_domain', None) or None,
    }
