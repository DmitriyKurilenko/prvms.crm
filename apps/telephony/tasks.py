from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from .models import CallRecord, SIPTrunk

logger = logging.getLogger(__name__)


@shared_task
def process_freeswitch_cdr(tenant_id: int, payload: dict):
    from apps.crm.models import Activity, Contact, Deal, Pipeline, Stage

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        started_at = _as_dt(payload.get('started_at')) or timezone.now()
        ended_at = _as_dt(payload.get('ended_at'))
        answered_at = _as_dt(payload.get('answered_at'))
        record, _ = CallRecord.objects.update_or_create(
            freeswitch_uuid=str(payload.get('uuid')),
            defaults={
                'direction': payload.get('direction', 'inbound'),
                'caller_number': payload.get('caller_number', ''),
                'called_number': payload.get('called_number', ''),
                'result': payload.get('result', 'missed'),
                'duration': int(payload.get('duration', 0)),
                'wait_time': int(payload.get('wait_time', 0)),
                'started_at': started_at,
                'answered_at': answered_at,
                'ended_at': ended_at,
            },
        )

        record_file_path = payload.get('record_file', '')
        if record_file_path:
            relative = _translate_recording_path(record_file_path)
            if relative:
                full = Path(settings.MEDIA_ROOT) / relative
                if full.exists():
                    record.record_file = relative
                    record.save(update_fields=['record_file'])
                    upload_call_record_to_crm.delay(tenant.id, record.id)

        if record.result == 'missed':
            create_lead_from_missed_call.delay(tenant.id, record.id)

        if tenant.crm_mode == 'builtin':
            contact, _ = Contact.objects.get_or_create(
                phone=record.caller_number,
                defaults={'first_name': 'Неизвестный клиент', 'source': 'telephony'},
            )
            pipeline = Pipeline.objects.filter(is_default=True).order_by('id').first() or Pipeline.objects.order_by('id').first()
            stage = None
            if pipeline:
                stage = pipeline.stages.order_by('sort_order', 'id').first() or Stage.objects.filter(pipeline=pipeline).order_by('id').first()
            if stage:
                deal, _ = Deal.objects.get_or_create(
                    name=f'Звонок {record.caller_number}',
                    pipeline=pipeline,
                    stage=stage,
                    contact=contact,
                    defaults={'source': 'telephony'},
                )
                Activity.objects.create(
                    activity_type='call',
                    deal=deal,
                    contact=contact,
                    title=f'Звонок {record.caller_number} → {record.called_number}',
                    body=f'Результат: {record.result}, длительность: {record.duration}s',
                    status='done',
                    related_call=record,
                )

        return {'id': record.id}


@shared_task
def check_sip_registrations():
    """Query FreeSWITCH ESL for actual SIP trunk registration status."""
    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    changed = 0
    registered_gateways = _get_registered_gateways()
    for tenant in tenants:
        with tenant_context(tenant):
            for trunk in SIPTrunk.objects.filter(is_active=True):
                is_registered = trunk.name in registered_gateways
                new_status = 'active' if is_registered else 'error'
                if trunk.status != new_status:
                    trunk.status = new_status
                    trunk.status_detail = 'Registered' if is_registered else 'Not registered on FreeSWITCH'
                    if is_registered:
                        trunk.last_registration_at = timezone.now()
                    trunk.save(update_fields=['status', 'status_detail', 'last_registration_at'])
                    changed += 1
    return {'updated': changed}


@shared_task
def upload_call_record_to_crm(tenant_id: int, call_record_id: int):
    """Upload call recording to CRM via adapter."""
    from apps.integrations.adapters import get_adapter_for_tenant

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        record = CallRecord.objects.get(id=call_record_id)
        if not record.record_file:
            return {'status': 'skipped', 'reason': 'no_record_file'}
        if record.record_uploaded_to_crm:
            return {'status': 'skipped', 'reason': 'already_uploaded'}

        try:
            adapter = get_adapter_for_tenant(tenant)
            record_url = record.record_file.url
            if record.crm_call_id:
                adapter.attach_call_record(record.crm_call_id, record_url)
            else:
                # Register call first, then attach
                call_data = {
                    'uuid': record.freeswitch_uuid,
                    'direction': record.direction,
                    'caller_number': record.caller_number,
                    'called_number': record.called_number,
                    'result': record.result,
                    'duration': record.duration,
                    'started_at': record.started_at.isoformat() if record.started_at else '',
                    'started_at_ts': int(record.started_at.timestamp()) if record.started_at else None,
                    'responsible_user_id': str(record.manager.crm_user_id) if record.manager_id and record.manager.crm_user_id else None,
                    'call_record_id': record.id,
                }
                crm_call_id = adapter.register_call(call_data)
                if crm_call_id:
                    record.crm_call_id = crm_call_id
                    adapter.attach_call_record(crm_call_id, record_url)

            record.record_uploaded_to_crm = True
            record.save(update_fields=['record_uploaded_to_crm', 'crm_call_id'])
            return {'status': 'ok', 'id': record.id}
        except Exception:
            logger.exception('Failed to upload call record %s to CRM for tenant %s', record.id, tenant.schema_name)
            return {'status': 'error', 'id': record.id}


@shared_task
def create_lead_from_missed_call(tenant_id: int, call_record_id: int):
    from apps.crm.models import Contact, Deal, Pipeline, Stage

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        record = CallRecord.objects.get(id=call_record_id)
        if record.result != 'missed' or tenant.crm_mode != 'builtin':
            return {'status': 'skipped'}

        contact, _ = Contact.objects.get_or_create(
            phone=record.caller_number,
            defaults={'first_name': 'Пропущенный звонок', 'source': 'telephony'},
        )
        pipeline = Pipeline.objects.filter(is_default=True).order_by('id').first() or Pipeline.objects.order_by('id').first()
        if not pipeline:
            return {'status': 'skipped', 'reason': 'no_pipeline'}
        stage = pipeline.stages.order_by('sort_order', 'id').first() or Stage.objects.filter(pipeline=pipeline).order_by('id').first()
        if not stage:
            return {'status': 'skipped', 'reason': 'no_stage'}
        deal = Deal.objects.create(
            name=f'Пропущенный звонок {record.caller_number}',
            pipeline=pipeline,
            stage=stage,
            contact=contact,
            source='missed_call',
        )
        return {'status': 'ok', 'deal_id': deal.id}


@shared_task
def sync_freeswitch_config(tenant_id: int, trunk_id: int):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        trunk = SIPTrunk.objects.get(id=trunk_id)
        # Gateway config is served dynamically via /telephony/configuration/ (xml_curl).
        # Trigger FreeSWITCH to reload its sofia profile and pick up the new gateway.
        rescan_ok = _esl_sofia_rescan()
        trunk.status = 'registering'
        trunk.status_detail = 'Rescan отправлен, ожидание регистрации.' if rescan_ok else 'ESL недоступен, rescan не выполнен.'
        trunk.save(update_fields=['status', 'status_detail'])
        return {'status': 'ok', 'trunk_id': trunk.id, 'rescan': rescan_ok}


def _as_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return None


def _get_esl_connection():
    """Create a greenswitch ESL inbound connection to FreeSWITCH."""
    import greenswitch
    conn = greenswitch.InboundESL(
        host=settings.FREESWITCH_ESL_HOST,
        port=settings.FREESWITCH_ESL_PORT,
        password=settings.FREESWITCH_ESL_PASSWORD,
    )
    conn.connect()
    return conn


def _get_registered_gateways() -> set[str]:
    """Query FreeSWITCH for currently registered SIP gateways."""
    try:
        conn = _get_esl_connection()
        ev = conn.send(f'api sofia status')
        body = ev.data.get('Body', '') if hasattr(ev, 'data') else str(ev)
        conn.stop()
        # Parse gateway names from sofia status output
        gateways = set()
        for line in body.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and 'REGED' in line.upper():
                # Format: gateway_name  profile  sip:...  REGED
                gateways.add(parts[0].strip())
        return gateways
    except Exception:
        # greenswitch raises plain Exception subclasses; broad catch is defense against
        # network/parse failures so SIP health checks degrade gracefully.
        logger.warning('Cannot connect to FreeSWITCH ESL to check registrations')
        return set()


def esl_originate(caller: str, destination: str, trunk_name: str | None = None, variables: dict | None = None) -> str:
    """Send originate command to FreeSWITCH via ESL. Returns call UUID."""
    import uuid as _uuid
    call_uuid = str(_uuid.uuid4())
    try:
        conn = _get_esl_connection()
        var_str = ''
        if variables:
            pairs = ','.join(f'{k}={v}' for k, v in variables.items())
            var_str = f'{{{pairs}}}'
        if trunk_name:
            originate_str = f'originate {var_str}sofia/gateway/{trunk_name}/{destination} &bridge(user/{caller})'
        else:
            originate_str = f'originate {var_str}user/{destination} &bridge(user/{caller})'
        ev = conn.send(f'api {originate_str}')
        body = ev.data.get('Body', '') if hasattr(ev, 'data') else str(ev)
        conn.stop()
        if 'ERR' in body.upper() or 'INVALID' in body.upper():
            logger.error('FreeSWITCH originate failed: %s', body)
        # If FS returned a UUID, use it
        stripped = body.strip()
        if stripped and '+OK' in stripped:
            # +OK <uuid>
            parts = stripped.split()
            if len(parts) >= 2:
                call_uuid = parts[-1]
        return call_uuid
    except Exception:
        logger.exception('FreeSWITCH ESL originate failed for %s -> %s', caller, destination)
        raise


def _translate_recording_path(fs_path: str) -> str | None:
    """Map a FreeSWITCH absolute recording path to a Django media-relative path."""
    path_map = getattr(settings, 'FREESWITCH_RECORDINGS_PATH_MAP', {})
    for fs_prefix, local_prefix in path_map.items():
        if fs_path.startswith(fs_prefix):
            return fs_path.replace(fs_prefix, local_prefix, 1)
    return None


def _esl_sofia_rescan() -> bool:
    """Send 'sofia rescan' via ESL so FreeSWITCH reloads gateway configs."""
    try:
        conn = _get_esl_connection()
        ev = conn.send('api sofia rescan')
        body = ev.data.get('Body', '') if hasattr(ev, 'data') else str(ev)
        conn.stop()
        return '+OK' in body or 'reloading' in body.lower()
    except Exception:
        # greenswitch raises plain Exception; absent rescan should not crash callers.
        logger.warning('FreeSWITCH ESL unavailable for sofia rescan')
        return False


def _check_gateway_status(name: str) -> tuple[bool, str]:
    """Query FreeSWITCH for a specific gateway's registration status."""
    conn = _get_esl_connection()
    ev = conn.send(f'api sofia status gateway {name}')
    body = ev.data.get('Body', '') if hasattr(ev, 'data') else str(ev)
    conn.stop()
    upper = body.upper()
    if 'REGED' in upper:
        return True, 'Зарегистрирован'
    if 'NOREG' in upper or 'FAILED' in upper:
        return False, 'Не зарегистрирован'
    return False, 'Шлюз не найден'


def _write_trunk_config(tenant_slug: str, trunk: SIPTrunk):
    base_path = Path('/app/media/telephony/freeswitch') / tenant_slug / 'trunks'
    base_path.mkdir(parents=True, exist_ok=True)
    config_name = slugify(trunk.name) or f'trunk-{trunk.id}'
    config_path = base_path / f'{trunk.id}_{config_name}.xml'
    creds = trunk.credentials or {}
    # tenant_slug variable propagates to every inbound channel via this gateway,
    # enabling Django /telephony/dialplan/ to resolve the correct tenant.
    xml = f"""<include>
  <gateway name="{trunk.name}">
    <param name="username" value="{creds.get('username', '')}"/>
    <param name="password" value="{creds.get('password', '')}"/>
    <param name="proxy" value="{creds.get('proxy', '')}"/>
    <param name="register" value="true"/>
    <variables>
      <variable name="tenant_slug" value="{tenant_slug}" direction="inbound"/>
    </variables>
  </gateway>
</include>
"""
    config_path.write_text(xml, encoding='utf-8')
