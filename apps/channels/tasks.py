from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django_tenants.utils import schema_context, tenant_context

from apps.integrations.adapters import get_adapter_for_tenant
from apps.tenants.models import Tenant

from .models import ChatSession, MessageLog, MessengerChannel
from .providers import normalize_incoming_payload, send_outgoing

if TYPE_CHECKING:
    # Импортируется только для аннотаций: рантайм-импорт Contact живёт внутри
    # функции, чтобы не тянуть tenant-модель CRM на уровень модуля.
    from apps.crm.models import Contact

logger = logging.getLogger(__name__)


def _broadcast_message(tenant_slug: str, channel_id: int, session: ChatSession, message: MessageLog):
    """Push new message to all WS subscribers of this channel."""
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        f'chat.{tenant_slug}.channel.{channel_id}',
        {
            'type': 'chat.message',
            'payload': {
                'type': 'chat.message',
                'session_id': session.id,
                'channel_id': channel_id,
                'message': {
                    'id': message.id,
                    'direction': message.direction,
                    'text': message.text,
                    'attachments': message.attachments,
                    'external_message_id': message.external_message_id,
                    'crm_message_id': message.crm_message_id,
                    'delivered': message.delivered,
                    'error': message.error,
                    'created_at': message.created_at.isoformat(),
                },
            },
        },
    )


def _broadcast_session_update(tenant_slug: str, channel_id: int, session: ChatSession):
    """Push session update (new session or last_message_at change)."""
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        f'chat.{tenant_slug}.channel.{channel_id}',
        {
            'type': 'chat.session_update',
            'payload': {
                'type': 'chat.session_update',
                'channel_id': channel_id,
                'session': {
                    'id': session.id,
                    'external_chat_id': session.external_chat_id,
                    'external_user_name': session.external_user_name,
                    'crm_contact_id': session.crm_contact_id,
                    'crm_chat_id': session.crm_chat_id,
                    'crm_lead_id': session.crm_lead_id,
                    'is_active': session.is_active,
                    'last_message_at': session.last_message_at.isoformat() if session.last_message_at else '',
                },
            },
        },
    )


def _find_pipeline_and_stage() -> tuple | None:
    """Find active pipeline and its first stage for deal creation.

    Returns (pipeline, stage) or logs the exact reason and returns None.
    """
    from apps.crm.models import Pipeline

    pipeline = (
        Pipeline.objects.filter(is_default=True, is_active=True).order_by('id').first()
        or Pipeline.objects.filter(is_active=True).order_by('id').first()
    )
    if not pipeline:
        logger.warning('No active Pipeline found; cannot create deal')
        return None
    stage = pipeline.stages.order_by('sort_order', 'id').first()
    if not stage:
        logger.warning('Pipeline %s has no stages; cannot create deal', pipeline.id)
        return None
    return pipeline, stage


def _build_contact(normalized: dict, channel: MessengerChannel, external_chat_id: str) -> 'Contact':
    """Get or create a CRM Contact from normalized incoming payload."""
    from apps.crm.models import Contact

    phone = str(normalized.get('phone', ''))
    name = str(normalized.get('username', 'Клиент'))[:100] or 'Клиент'

    if phone:
        contact, _ = Contact.objects.get_or_create(
            phone=phone,
            defaults={'first_name': name, 'source': channel.channel_type},
        )
    else:
        messenger_key = f'{channel.channel_type}:{external_chat_id}'
        contact, _ = Contact.objects.get_or_create(
            messenger_id=messenger_key,
            defaults={'first_name': name, 'source': channel.channel_type},
        )
        if not contact.messenger_id:
            contact.messenger_id = messenger_key
            contact.save(update_fields=['messenger_id'])
    return contact


def _auto_create_lead(
    channel: MessengerChannel,
    session: ChatSession,
    message: MessageLog,
    normalized: dict,
    external_chat_id: str,
) -> None:
    """Create a Deal + Contact for a builtin-CRM tenant.

    Writes *message.error* and sets *delivered=False* when creation
    is impossible due to missing pipeline/stage so that ops can see
    the failure in the UI / logs.
    """
    from apps.crm.models import Deal
    from apps.distribution.services import ensure_builtin_manager_profiles, try_distribute

    contact = _build_contact(normalized, channel, external_chat_id)
    result = _find_pipeline_and_stage()
    if result is None:
        message.error = 'Воронка или этап не настроены — сделка не создана'
        message.delivered = False
        message.save(update_fields=['error', 'delivered'])
        return
    pipeline, stage = result

    deal = Deal.objects.create(
        name=f'Диалог {channel.name}: {external_chat_id}',
        pipeline=pipeline,
        stage=stage,
        contact=contact,
        source=channel.channel_type,
    )
    session.crm_lead_id = str(deal.id)
    session.crm_contact_id = str(contact.id)
    session.save(update_fields=['crm_lead_id', 'crm_contact_id'])
    if not deal.responsible_id:
        ensure_builtin_manager_profiles()
        try_distribute('new_deal', 'deal', str(deal.id))


def _sync_to_external_crm(
    tenant: Tenant,
    channel: MessengerChannel,
    session: ChatSession,
    message: MessageLog,
    external_chat_id: str,
) -> None:
    """Forward incoming message to an external CRM adapter."""
    adapter = get_adapter_for_tenant(tenant)
    if not session.crm_chat_id:
        session.crm_chat_id = adapter.register_chat_channel(str(channel.id), channel.name, '')
        session.save(update_fields=['crm_chat_id'])
    crm_message_id = adapter.send_message_to_crm(
        scope_id=session.crm_contact_id or external_chat_id,
        chat_id=session.crm_chat_id or external_chat_id,
        sender={'name': session.external_user_name or 'Client'},
        text=message.text,
        attachments=message.attachments,
    )
    if crm_message_id:
        message.crm_message_id = str(crm_message_id)
        message.save(update_fields=['crm_message_id'])


@shared_task
def route_incoming_message(tenant_id: int, channel_id: int, payload: dict):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        channel = MessengerChannel.objects.get(id=channel_id, is_active=True)
        normalized = normalize_incoming_payload(channel.channel_type, payload)
        if normalized is None:
            logger.info('Ignoring unsupported update type for channel %s', channel_id)
            return {'status': 'ignored', 'reason': 'unsupported_update_type'}
        external_chat_id = str(normalized.get('chat_id', 'unknown'))
        session, _ = ChatSession.objects.get_or_create(
            channel=channel,
            external_chat_id=external_chat_id,
            defaults={
                'external_user_name': str(normalized.get('username', '')),
                'is_active': True,
            },
        )

        message = MessageLog.objects.create(
            chat_session=session,
            direction='in',
            text=str(normalized.get('text', '')),
            attachments=normalized.get('attachments', []),
            external_message_id=str(normalized.get('message_id', '')),
        )
        session.save(update_fields=['last_message_at'])
        session.refresh_from_db()
        _broadcast_message(tenant.slug, channel_id, session, message)
        _broadcast_session_update(tenant.slug, channel_id, session)

        if channel.auto_create_lead and not session.crm_lead_id and tenant.crm_mode == 'builtin':
            try:
                _auto_create_lead(channel, session, message, normalized, external_chat_id)
            except Exception:
                logger.exception('Auto-create lead failed for channel %s message %s', channel.id, message.id)
                message.error = 'Ошибка при автоматическом создании сделки'
                message.delivered = False
                message.save(update_fields=['error', 'delivered'])
        elif channel.auto_create_lead and tenant.crm_mode != 'builtin':
            try:
                _sync_to_external_crm(tenant, channel, session, message, external_chat_id)
            except Exception:
                logger.exception('CRM sync failed for message %s on tenant %s', message.id, tenant.schema_name)
                message.error = 'Ошибка синхронизации с внешней CRM'
                message.delivered = False
                message.save(update_fields=['error', 'delivered'])

        return {'status': 'ok', 'message_id': message.id, 'session_id': session.id}


@shared_task
def poll_email_channels():
    """Beat: опрашивает все email-каналы во всех тенантах и подаёт новые письма
    в общий конвейер `route_incoming_message`. Дедуп по `Message-ID`.

    Стык [граница]: реальный IMAP-сервер (изолирован в `email_poller`).
    """
    from .email_poller import fetch_new_messages

    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))

    dispatched = 0
    for tenant in tenants:
        with tenant_context(tenant):
            channels = MessengerChannel.objects.filter(channel_type='email', is_active=True)
            if not channels:
                continue
            for channel in channels:
                try:
                    messages = fetch_new_messages(channel.credentials or {})
                except Exception as exc:  # noqa: BLE001 — граница IMAP: фиксируем, не глотаем
                    channel.status = 'error'
                    channel.status_detail = str(exc)[:500]
                    channel.save(update_fields=['status', 'status_detail'])
                    logger.exception('email poll failed for channel %s', channel.id)
                    continue
                for msg in messages:
                    msgid = str(msg.get('message_id') or '')
                    if msgid and MessageLog.objects.filter(external_message_id=msgid).exists():
                        continue  # дедуп по Message-ID
                    route_incoming_message.delay(tenant.id, channel.id, msg)
                    dispatched += 1
    return {'dispatched': dispatched}


@shared_task
def route_outgoing_message(tenant_id: int, channel_id: int, chat_session_id: int, payload: dict):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        channel = MessengerChannel.objects.get(id=channel_id, is_active=True)
        session = ChatSession.objects.get(id=chat_session_id, channel=channel)
        text = str(payload.get('text', payload.get('message', '')))
        attachments = payload.get('attachments', [])

        delivered, result = send_outgoing(channel, session.external_chat_id, text, attachments)
        message = MessageLog.objects.create(
            chat_session=session,
            direction='out',
            text=text,
            attachments=attachments,
            crm_message_id=str(payload.get('crm_message_id', '')),
            external_message_id=result if delivered else '',
            delivered=delivered,
            error='' if delivered else result,
        )
        session.save(update_fields=['last_message_at'])
        session.refresh_from_db()
        _broadcast_message(tenant.slug, channel_id, session, message)
        _broadcast_session_update(tenant.slug, channel_id, session)
        return {'status': 'ok' if delivered else 'error', 'message_id': message.id, 'result': result}
