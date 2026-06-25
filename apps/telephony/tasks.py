"""Фоновые задачи телефонии Exolve: обработка Call Events и запись разговоров."""
from __future__ import annotations

import logging
from datetime import datetime

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant

from .exolve_client import ExolveClient, ExolveError
from .models import CallRecord, CallTranscript

logger = logging.getLogger(__name__)


def _as_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def _ms_to_s(value) -> int:
    try:
        return int(value) // 1000
    except (TypeError, ValueError):
        return 0


@shared_task
def process_exolve_event(tenant_id: int, payload: dict):
    """Обновить журнал звонка по событию Call Events (b/o/s/h/d/e/crr)."""
    event_type = str(payload.get('type', ''))
    call_sid = str(payload.get('call_sid', ''))
    if not call_sid:
        return {'status': 'skipped', 'reason': 'no_call_sid'}

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        caller = str(payload.get('from') or payload.get('calling_number') or '')
        called = str(payload.get('to') or payload.get('called_number') or '')
        defaults = {
            'caller_number': caller,
            'called_number': called,
            'started_at': _as_dt(payload.get('date_time')) or timezone.now(),
        }
        record, created = CallRecord.objects.get_or_create(
            call_sid=call_sid,
            defaults={**defaults, 'direction': 'inbound', 'result': 'missed'},
        )
        record.exolve_call_id = str(payload.get('call_id') or record.exolve_call_id)

        if event_type == 'b':  # начало входящего вызова → сделка с контролем дублей
            record.direction = 'inbound'
            try:
                from apps.telephony.exolve_service import register_inbound_deal
                contact, deal, manager_profile = register_inbound_deal(caller, called)
                if contact:
                    record.crm_contact_id = str(contact.id)
                if deal:
                    record.crm_lead_id = str(deal.id)
                if manager_profile:
                    record.manager = manager_profile
            except Exception:
                logger.exception('Exolve inbound deal creation failed for call_sid %s', call_sid)

        if event_type == 's':  # ответ стороны B
            record.answered_at = _as_dt(payload.get('date_time')) or timezone.now()
            record.result = 'answered'
        elif event_type == 'd':  # окончание с метриками
            record.duration = _ms_to_s(payload.get('duration'))
            record.wait_time = _ms_to_s(payload.get('wait_time'))
            record.talk_time = _ms_to_s(payload.get('talk_time'))
            record.cause_code = str(payload.get('cause_code', ''))
            record.result = 'answered' if record.talk_time > 0 else 'missed'
        elif event_type == 'e':  # окончание вызова
            record.ended_at = _as_dt(payload.get('date_time')) or timezone.now()
        elif event_type == 'crr':  # запись готова
            record.ended_at = record.ended_at or timezone.now()

        record.save()

        if event_type == 'crr':
            path = payload.get('path')
            if path:
                download_call_record.delay(tenant.id, record.id, path)

        return {'status': 'ok', 'id': record.id, 'event': event_type, 'created': created}


@shared_task
def download_call_record(tenant_id: int, call_record_id: int, path: str):
    """Скачать запись разговора из Exolve и сохранить в media."""
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        try:
            record = CallRecord.objects.get(id=call_record_id)
        except CallRecord.DoesNotExist:
            return {'status': 'skipped', 'reason': 'no_record'}
        if record.record_file:
            return {'status': 'skipped', 'reason': 'already_downloaded'}
        try:
            content = ExolveClient().download_record(path)
        except ExolveError:
            logger.exception('Не удалось скачать запись звонка %s', call_record_id)
            return {'status': 'error'}
        record.record_file.save(f'{record.call_sid}.mp3', ContentFile(content), save=True)
        # Запускаем распознавание, если ключ Deepgram настроен (фичу тенанта
        # проверяет сама задача транскрипции).
        from django.conf import settings
        if settings.DEEPGRAM_API_KEY:
            transcribe_call_record.delay(tenant.id, record.id)
        return {'status': 'ok', 'id': record.id}


def _ai_call_intelligence_enabled(tenant) -> bool:
    """Проверка фичи `ai_call_intelligence` на уровне тарифа тенанта (public-схема)."""
    from apps.billing.models import Plan
    with schema_context('public'):
        return bool(tenant.plan_id) and Plan.objects.filter(
            id=tenant.plan_id, features__code='ai_call_intelligence',
        ).exists()


@shared_task(autoretry_for=(ExolveError,), retry_backoff=True, max_retries=2)
def transcribe_call_record(tenant_id: int, call_record_id: int):
    """Распознаёт запись звонка через Deepgram и ставит задачу резюме.
    Идемпотентна: повторный запуск по готовой транскрипции пропускается."""
    from .deepgram_client import DeepgramError, transcribe

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    if not _ai_call_intelligence_enabled(tenant):
        return {'status': 'skipped', 'reason': 'feature_disabled'}

    with tenant_context(tenant):
        try:
            record = CallRecord.objects.get(id=call_record_id)
        except CallRecord.DoesNotExist:
            return {'status': 'skipped', 'reason': 'no_record'}
        if not record.record_file:
            return {'status': 'skipped', 'reason': 'no_audio'}

        transcript, _ = CallTranscript.objects.get_or_create(call=record)
        if transcript.status == 'done':
            return {'status': 'skipped', 'reason': 'already_done'}
        transcript.status = 'processing'
        transcript.save(update_fields=['status', 'updated_at'])

        try:
            audio = record.record_file.read()
            result = transcribe(audio, content_type='audio/mpeg')
        except (DeepgramError, OSError) as exc:
            transcript.status = 'failed'
            transcript.error = str(exc)[:500]
            transcript.save(update_fields=['status', 'error', 'updated_at'])
            logger.warning('Транскрипция звонка %s провалена: %s', call_record_id, exc)
            return {'status': 'failed', 'reason': str(exc)[:200]}

        transcript.text = result['text']
        transcript.confidence = result['confidence']
        transcript.language = result['language'] or ''
        transcript.status = 'done'
        transcript.error = ''
        transcript.save()
        summarize_call.delay(tenant_id, transcript.id)
        return {'status': 'ok', 'transcript_id': transcript.id, 'chars': len(transcript.text)}


@shared_task
def summarize_call(tenant_id: int, transcript_id: int):
    """Формирует AI-резюме транскрипта через Hermes и кладёт его активностью
    в таймлайн сделки."""
    from apps.ai_assistant.services import summarize_call_text
    from apps.crm.models import Activity

    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        try:
            transcript = CallTranscript.objects.select_related('call').get(id=transcript_id)
        except CallTranscript.DoesNotExist:
            return {'status': 'skipped', 'reason': 'no_transcript'}
        if not transcript.text:
            return {'status': 'skipped', 'reason': 'empty_text'}

        try:
            summary = summarize_call_text(tenant, transcript.text)
        except Exception as exc:  # noqa: BLE001 — граница LLM: логируем, не роняем цепочку
            logger.warning('Резюме звонка для транскрипта %s не получено: %s', transcript_id, exc)
            return {'status': 'failed', 'reason': str(exc)[:200]}

        transcript.summary = summary
        transcript.save(update_fields=['summary', 'updated_at'])

        record = transcript.call
        deal_id = int(record.crm_lead_id) if (record.crm_lead_id or '').isdigit() else None
        if deal_id and summary:
            Activity.objects.create(
                activity_type='note',
                deal_id=deal_id,
                related_call=record,
                title='Резюме звонка',
                body=summary,
                status='done',
            )
        return {'status': 'ok', 'transcript_id': transcript.id, 'activity_deal': deal_id}
