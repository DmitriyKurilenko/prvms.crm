from __future__ import annotations

from collections import defaultdict

from apps.audit.services import log_event
from apps.core.access import (
    filter_crm_queryset_by_scope,
    normalize_crm_responsible_for_write,
    require_crm_permission,
)
from apps.core.tenant import get_request_tenant
from apps.distribution.services import ensure_builtin_manager_profiles, try_distribute
from apps.notifications.services import notify

from ._api_common import (
    _apply_responsible_write_guard,
    _ensure_builtin,
    _scoped_object_or_error,
    _serialize_activities,
    crm_router,
)
from .models import Activity, Company, Contact, Deal, Stage
from .schemas import DealIn, DealMoveIn, DealPatchIn
from .services.auto_actions import process_stage_change


@crm_router.get('/deals/')
def list_deals(
    request,
    pipeline_id: int | None = None,
    stage_id: int | None = None,
    responsible_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    qs = filter_crm_queryset_by_scope(
        request,
        Deal.objects.select_related('stage', 'pipeline', 'contact', 'responsible').all(),
        'deals',
    ).order_by('-updated_at')
    if pipeline_id:
        qs = qs.filter(pipeline_id=pipeline_id)
    if stage_id:
        qs = qs.filter(stage_id=stage_id)
    if responsible_id:
        qs = qs.filter(responsible_id=responsible_id)
    if date_from:
        qs = qs.filter(updated_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(updated_at__date__lte=date_to)
    return [
        {
            'id': d.id,
            'name': d.name,
            'pipeline_id': d.pipeline_id,
            'stage_id': d.stage_id,
            'stage_name': d.stage.name,
            'amount': float(d.amount) if d.amount is not None else None,
            'currency': d.currency,
            'responsible_id': d.responsible_id,
            'contact_id': d.contact_id,
            'updated_at': d.updated_at.isoformat(),
        }
        for d in qs
    ]


@crm_router.get('/deals/kanban/{pipeline_id}/')
def kanban_deals(request, pipeline_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    stages = Stage.objects.filter(pipeline_id=pipeline_id).order_by('sort_order')
    deals = filter_crm_queryset_by_scope(
        request,
        Deal.objects.filter(pipeline_id=pipeline_id).select_related('stage'),
        'deals',
    )
    grouped = defaultdict(list)
    for deal in deals:
        grouped[deal.stage_id].append(
            {
                'id': deal.id,
                'name': deal.name,
                'amount': float(deal.amount) if deal.amount is not None else None,
                'currency': deal.currency,
                'responsible_id': deal.responsible_id,
                'contact_id': deal.contact_id,
                'company_id': deal.company_id,
                'source': deal.source,
                'created_at': deal.created_at.isoformat(),
            }
        )
    return [{'stage': {'id': s.id, 'name': s.name, 'color': s.color}, 'deals': grouped.get(s.id, [])} for s in stages]


@crm_router.post('/deals/')
def create_deal(request, payload: DealIn):
    require_crm_permission(request, 'deals', 'create')
    _ensure_builtin(request)
    data = payload.dict()
    _apply_responsible_write_guard(request, data, entity='deals', action='create', default_on_own=True)
    deal = Deal.objects.create(
        name=data['name'],
        pipeline_id=data['pipeline_id'],
        stage_id=data['stage_id'],
        contact_id=data['contact_id'],
        company_id=data['company_id'],
        amount=data['amount'],
        currency=data['currency'],
        responsible_id=data['responsible_id'],
        expected_close_date=data['expected_close_date'],
        loss_reason=data['loss_reason'],
        custom_fields=data['custom_fields'],
        source=data['source'],
    )
    Activity.objects.create(
        activity_type='system',
        deal=deal,
        title='Сделка создана',
        body=f'Стадия: {deal.stage.name}',
        status='done',
        created_by=request.auth,
    )
    # Auto-distribute if no responsible assigned
    if not deal.responsible_id:
        ensure_builtin_manager_profiles()
        log = try_distribute('new_deal', 'deal', str(deal.id))
        if log and log.assigned_to_id:
            deal.refresh_from_db()
    log_event(request, action='create', instance=deal)
    tenant = get_request_tenant(request)
    notify(tenant, 'new_deal_created', {'deal_id': deal.id, 'link': '/crm'})
    return {'id': deal.id}


@crm_router.get('/deals/{deal_id}/')
def get_deal(request, deal_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    d = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='view')
    activities = Activity.objects.filter(deal_id=deal_id).order_by('-created_at')[:100]
    from apps.channels.models import ChatSession as ChannelChatSession
    from apps.documents.models import Document, SigningSession
    deal_documents = list(Document.objects.filter(deal=d).order_by('-created_at'))
    session_map = {}
    if deal_documents:
        for s in SigningSession.objects.filter(document__in=deal_documents).order_by('document_id', '-otp_sent_at'):
            if s.document_id not in session_map:
                session_map[s.document_id] = s.token
    # Chat sessions linked to this deal via crm_lead_id
    chat_sessions = ChannelChatSession.objects.filter(
        crm_lead_id=str(d.id),
    ).select_related('channel').order_by('-last_message_at')
    base_url = f'{request.scheme}://{request.get_host()}'
    return {
        'id': d.id,
        'name': d.name,
        'pipeline_id': d.pipeline_id,
        'stage_id': d.stage_id,
        'contact_id': d.contact_id,
        'company_id': d.company_id,
        'amount': float(d.amount) if d.amount is not None else None,
        'currency': d.currency,
        'responsible_id': d.responsible_id,
        'expected_close_date': d.expected_close_date.isoformat() if d.expected_close_date else None,
        'source': d.source,
        'loss_reason': d.loss_reason,
        'activities': [
            {'id': a.id, 'type': a.activity_type, 'title': a.title, 'body': a.body, 'status': a.status, 'created_at': a.created_at.isoformat()}
            for a in activities
        ],
        'documents': [
            {'id': doc.id, 'template_name': doc.template.name if doc.template else None, 'status': doc.status, 'created_at': doc.created_at.isoformat(), 'contact_phone': d.contact.phone if d.contact else '', 'signing_url': f'{base_url}/sign/{session_map[doc.id]}/' if doc.id in session_map else None}
            for doc in deal_documents
        ],
        'chat_sessions': [
            {
                'id': cs.id,
                'channel_id': cs.channel_id,
                'channel_name': cs.channel.name if cs.channel else '',
                'channel_type': cs.channel.channel_type if cs.channel else '',
                'external_user_name': cs.external_user_name,
                'external_chat_id': cs.external_chat_id,
                'last_message_at': cs.last_message_at.isoformat() if cs.last_message_at else None,
                'is_active': cs.is_active,
            }
            for cs in chat_sessions
        ],
    }


@crm_router.patch('/deals/{deal_id}/')
def patch_deal(request, deal_id: int, payload: DealPatchIn):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    changes = payload.dict(exclude_unset=True)
    if not changes:
        return {'detail': 'ok'}

    # При наличии позиций сумма сделки производная (Σ позиций), ручной ввод игнорируем.
    if 'amount' in changes and deal.items.exists():
        changes.pop('amount')

    if 'responsible_id' in changes:
        changes['responsible_id'] = normalize_crm_responsible_for_write(
            request,
            entity='deals',
            action='update',
            responsible_id=changes.get('responsible_id'),
            default_to_actor_on_own=False,
        )

    field_labels = {
        'name': 'Название', 'amount': 'Сумма', 'currency': 'Валюта',
        'contact_id': 'Контакт', 'company_id': 'Компания', 'responsible_id': 'Ответственный',
        'expected_close_date': 'Дата закрытия', 'source': 'Источник', 'loss_reason': 'Причина проигрыша',
        'custom_fields': 'Доп. поля',
    }

    def _display_val(field, val):
        if val is None:
            return '—'
        if field == 'contact_id':
            try:
                return str(Contact.objects.get(id=val))
            except Contact.DoesNotExist:
                return str(val)
        if field == 'company_id':
            try:
                return Company.objects.get(id=val).name
            except Company.DoesNotExist:
                return str(val)
        if field == 'responsible_id':
            from apps.users.models import User
            try:
                u = User.objects.get(id=val)
                return u.get_full_name() or u.username
            except User.DoesNotExist:
                return str(val)
        return str(val)

    def _normalize(field, val):
        if val is None:
            return None
        if field == 'amount':
            return float(val)
        if field == 'expected_close_date':
            return str(val)
        return val

    changed_lines = []
    audit_changes = {}
    for field, new_val in changes.items():
        if field not in field_labels:
            continue
        old_val = getattr(deal, field, None)
        if _normalize(field, old_val) == _normalize(field, new_val):
            continue
        label = field_labels[field]
        old_display = _display_val(field, old_val)
        new_display = _display_val(field, new_val)
        changed_lines.append(f'{label}: {old_display} → {new_display}')
        audit_changes[label] = {'before': old_display, 'after': new_display}

    Deal.objects.filter(id=deal_id).update(**changes)

    if changed_lines:
        Activity.objects.create(
            activity_type='system',
            deal=deal,
            title='Сделка обновлена',
            body='\n'.join(changed_lines),
            status='done',
            created_by=request.auth,
        )
    if audit_changes:
        deal.refresh_from_db()
        log_event(request, action='update', instance=deal, changes=audit_changes)
    return {'detail': 'ok'}


@crm_router.patch('/deals/{deal_id}/move/')
def move_deal(request, deal_id: int, payload: DealMoveIn):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    old_stage = deal.stage
    new_stage = Stage.objects.get(id=payload.stage_id, pipeline_id=deal.pipeline_id)
    deal.stage = new_stage
    deal.save(update_fields=['stage'])
    Activity.objects.create(
        activity_type='stage_change',
        deal=deal,
        title=f'{old_stage.name} → {new_stage.name}',
        body=f'Сделка перемещена в стадию «{new_stage.name}»',
        status='done',
        created_by=request.auth,
    )
    log_event(request, action='update', instance=deal,
              changes={'Стадия': {'before': old_stage.name, 'after': new_stage.name}})
    process_stage_change(deal, old_stage, new_stage)
    tenant = get_request_tenant(request)
    notify(tenant, 'deal_stage_changed', {'deal_id': deal.id, 'link': '/crm'})
    return {'detail': 'ok'}


@crm_router.delete('/deals/{deal_id}/')
def delete_deal(request, deal_id: int):
    require_crm_permission(request, 'deals', 'delete')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='delete')
    log_event(request, action='delete', instance=deal)
    Deal.objects.filter(id=deal_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/deals/{deal_id}/activities/')
def deal_activities(request, deal_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='view')
    return _serialize_activities(Activity.objects.filter(deal_id=deal_id).order_by('-created_at'))
