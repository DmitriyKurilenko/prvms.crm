from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q, Sum
from ninja import Field, Router, Schema
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.billing.guards import check_limit
from apps.core.access import (
    ensure_crm_object_scope,
    filter_crm_queryset_by_scope,
    normalize_crm_responsible_for_write,
    require_crm_permission,
    require_feature_access,
    require_roles,
)
from apps.core.tenant import get_request_tenant
from .models import Activity, Company, Contact, Deal, Pipeline, Stage
from .services.auto_actions import process_stage_change
from apps.distribution.services import ensure_builtin_manager_profiles, try_distribute
from apps.users.models import Membership
from apps.audit.services import log_event
from apps.notifications.services import notify

crm_router = Router(tags=['crm'], auth=JWTAuth())


def _ensure_builtin(request):
    tenant = get_request_tenant(request)
    require_feature_access(request, 'crm_builtin')
    if tenant.crm_mode != 'builtin':
        raise HttpError(400, 'Builtin CRM API is available only for crm_mode=builtin')


def _scoped_object_or_error(request, model, obj_id: int, entity: str, action: str):
    obj = model.objects.filter(id=obj_id).first()
    if obj is None:
        raise HttpError(404, 'Not found')
    ensure_crm_object_scope(request, entity, action, obj)
    return obj


def _apply_responsible_write_guard(request, payload_data: dict, entity: str, action: str, *, default_on_own: bool):
    payload_data['responsible_id'] = normalize_crm_responsible_for_write(
        request,
        entity=entity,
        action=action,
        responsible_id=payload_data.get('responsible_id'),
        default_to_actor_on_own=default_on_own,
    )


class ContactIn(Schema):
    first_name: str
    last_name: str = ''
    phone: str = ''
    email: str = ''
    messenger_id: str = ''
    position: str = ''
    company_id: int | None = None
    custom_fields: dict = {}
    source: str = ''
    responsible_id: int | None = None


class ContactPatchIn(Schema):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    messenger_id: str | None = None
    position: str | None = None
    company_id: int | None = None
    custom_fields: dict | None = None
    source: str | None = None
    responsible_id: int | None = None


class CompanyIn(Schema):
    name: str
    inn: str = Field('', max_length=12)
    phone: str = Field('', max_length=50)
    email: str = ''
    address: str = ''
    website: str = ''
    custom_fields: dict = {}
    responsible_id: int | None = None


class CompanyPatchIn(Schema):
    name: str | None = None
    inn: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    website: str | None = None
    custom_fields: dict | None = None
    responsible_id: int | None = None


class PipelineIn(Schema):
    name: str
    is_default: bool = False
    sort_order: int = 0
    is_active: bool = True


class PipelinePatchIn(Schema):
    name: str | None = None
    is_default: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class StageIn(Schema):
    name: str
    stage_type: str = 'open'
    color: str = '#3B82F6'
    sort_order: int = 0
    auto_action: dict = {}


class StagePatchIn(Schema):
    name: str | None = None
    stage_type: str | None = None
    color: str | None = None
    sort_order: int | None = None
    auto_action: dict | None = None


class DealIn(Schema):
    name: str
    pipeline_id: int
    stage_id: int
    contact_id: int | None = None
    company_id: int | None = None
    amount: float | None = None
    currency: str = 'RUB'
    responsible_id: int | None = None
    expected_close_date: str | None = None
    loss_reason: str = ''
    custom_fields: dict = {}
    source: str = ''


class DealPatchIn(Schema):
    name: str | None = None
    pipeline_id: int | None = None
    stage_id: int | None = None
    contact_id: int | None = None
    company_id: int | None = None
    amount: float | None = None
    currency: str | None = None
    responsible_id: int | None = None
    expected_close_date: str | None = None
    loss_reason: str | None = None
    custom_fields: dict | None = None
    source: str | None = None


class DealMoveIn(Schema):
    stage_id: int


class ActivityIn(Schema):
    activity_type: str
    deal_id: int | None = None
    contact_id: int | None = None
    responsible_id: int | None = None
    title: str
    body: str = ''
    status: str = 'done'
    due_date: str | None = None


class ActivityPatchIn(Schema):
    activity_type: str | None = None
    deal_id: int | None = None
    contact_id: int | None = None
    responsible_id: int | None = None
    title: str | None = None
    body: str | None = None
    status: str | None = None
    due_date: str | None = None


@crm_router.get('/managers/')
def list_managers(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    _ensure_builtin(request)
    tenant = get_request_tenant(request)
    members = (
        Membership.objects
        .filter(tenant=tenant, is_active=True)
        .exclude(role='viewer')
        .select_related('user')
        .order_by('user__first_name', 'user__email')
    )
    return [
        {'id': m.user_id, 'name': m.user.get_full_name() or m.user.email}
        for m in members
    ]


@crm_router.get('/contacts/')
def list_contacts(request, q: str | None = None):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    qs = filter_crm_queryset_by_scope(request, Contact.objects.all(), 'contacts').order_by('-created_at')
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q))
    return [
        {
            'id': c.id,
            'first_name': c.first_name,
            'last_name': c.last_name,
            'phone': c.phone,
            'email': c.email,
            'company_id': c.company_id,
            'responsible_id': c.responsible_id,
            'created_at': c.created_at.isoformat(),
            'esign_agreement_signed_at': c.esign_agreement_signed_at.isoformat() if c.esign_agreement_signed_at else None,
        }
        for c in qs
    ]


@crm_router.post('/contacts/')
def create_contact(request, payload: ContactIn):
    require_crm_permission(request, 'contacts', 'create')
    _ensure_builtin(request)
    data = payload.dict()
    _apply_responsible_write_guard(request, data, entity='contacts', action='create', default_on_own=True)
    c = Contact.objects.create(**data)
    log_event(request, action='create', instance=c)
    return {'id': c.id}


@crm_router.get('/contacts/{contact_id}/')
def get_contact(request, contact_id: int):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    c = _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='view')
    activities = Activity.objects.filter(contact_id=contact_id).order_by('-created_at')[:100]
    return {
        'id': c.id,
        'first_name': c.first_name,
        'last_name': c.last_name,
        'phone': c.phone,
        'email': c.email,
        'company_id': c.company_id,
        'custom_fields': c.custom_fields,
        'source': c.source,
        'responsible_id': c.responsible_id,
        'esign_agreement_signed_at': c.esign_agreement_signed_at.isoformat() if c.esign_agreement_signed_at else None,
        'esign_agreement_id': c.esign_agreement_id,
        'activities': [
            {'id': a.id, 'type': a.activity_type, 'title': a.title, 'status': a.status, 'created_at': a.created_at.isoformat()}
            for a in activities
        ],
    }


@crm_router.patch('/contacts/{contact_id}/')
def patch_contact(request, contact_id: int, payload: ContactPatchIn):
    require_crm_permission(request, 'contacts', 'update')
    _ensure_builtin(request)
    contact = _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='update')
    changes = payload.dict(exclude_unset=True)
    if 'responsible_id' in changes:
        changes['responsible_id'] = normalize_crm_responsible_for_write(
            request,
            entity='contacts',
            action='update',
            responsible_id=changes.get('responsible_id'),
            default_to_actor_on_own=False,
        )
    audit_changes = {k: {'before': str(getattr(contact, k, None)), 'after': str(v)} for k, v in changes.items()}
    Contact.objects.filter(id=contact_id).update(**changes)
    if audit_changes:
        contact.refresh_from_db()
        log_event(request, action='update', instance=contact, changes=audit_changes)
    return {'detail': 'ok'}


@crm_router.delete('/contacts/{contact_id}/')
def delete_contact(request, contact_id: int):
    require_crm_permission(request, 'contacts', 'delete')
    _ensure_builtin(request)
    contact = _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='delete')
    log_event(request, action='delete', instance=contact)
    Contact.objects.filter(id=contact_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/companies/')
def list_companies(request, q: str | None = None):
    require_crm_permission(request, 'companies', 'view')
    _ensure_builtin(request)
    qs = filter_crm_queryset_by_scope(request, Company.objects.all(), 'companies').order_by('-created_at')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(inn__icontains=q))
    return [
        {'id': c.id, 'name': c.name, 'inn': c.inn, 'phone': c.phone, 'email': c.email, 'created_at': c.created_at.isoformat()}
        for c in qs
    ]


@crm_router.post('/companies/')
def create_company(request, payload: CompanyIn):
    require_crm_permission(request, 'companies', 'create')
    _ensure_builtin(request)
    data = payload.dict()
    _apply_responsible_write_guard(request, data, entity='companies', action='create', default_on_own=True)
    c = Company.objects.create(**data)
    log_event(request, action='create', instance=c)
    return {'id': c.id}


@crm_router.get('/companies/{company_id}/')
def get_company(request, company_id: int):
    require_crm_permission(request, 'companies', 'view')
    _ensure_builtin(request)
    c = _scoped_object_or_error(request, Company, company_id, entity='companies', action='view')
    return {
        'id': c.id,
        'name': c.name,
        'inn': c.inn,
        'phone': c.phone,
        'email': c.email,
        'contacts_count': c.contacts.count(),
        'deals_count': c.deals.count(),
    }


@crm_router.patch('/companies/{company_id}/')
def patch_company(request, company_id: int, payload: CompanyPatchIn):
    require_crm_permission(request, 'companies', 'update')
    _ensure_builtin(request)
    company = _scoped_object_or_error(request, Company, company_id, entity='companies', action='update')
    changes = payload.dict(exclude_unset=True)
    if 'responsible_id' in changes:
        changes['responsible_id'] = normalize_crm_responsible_for_write(
            request,
            entity='companies',
            action='update',
            responsible_id=changes.get('responsible_id'),
            default_to_actor_on_own=False,
        )
    audit_changes = {k: {'before': str(getattr(company, k, None)), 'after': str(v)} for k, v in changes.items()}
    Company.objects.filter(id=company_id).update(**changes)
    if audit_changes:
        company.refresh_from_db()
        log_event(request, action='update', instance=company, changes=audit_changes)
    return {'detail': 'ok'}


@crm_router.delete('/companies/{company_id}/')
def delete_company(request, company_id: int):
    require_crm_permission(request, 'companies', 'delete')
    _ensure_builtin(request)
    company = _scoped_object_or_error(request, Company, company_id, entity='companies', action='delete')
    log_event(request, action='delete', instance=company)
    Company.objects.filter(id=company_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/pipelines/')
def list_pipelines(request):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    return [
        {'id': p.id, 'name': p.name, 'is_default': p.is_default, 'sort_order': p.sort_order, 'is_active': p.is_active}
        for p in Pipeline.objects.all().order_by('sort_order', 'id')
    ]


@crm_router.post('/pipelines/')
def create_pipeline(request, payload: PipelineIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    tenant = get_request_tenant(request)
    current = Pipeline.objects.count()
    if not check_limit(tenant, 'max_pipelines', current):
        return 400, {'detail': 'Pipeline limit reached'}
    p = Pipeline.objects.create(**payload.dict())
    return {'id': p.id}


@crm_router.patch('/pipelines/{pipeline_id}/')
def patch_pipeline(request, pipeline_id: int, payload: PipelinePatchIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    Pipeline.objects.filter(id=pipeline_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@crm_router.delete('/pipelines/{pipeline_id}/')
def delete_pipeline(request, pipeline_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    if Deal.objects.filter(pipeline_id=pipeline_id).exists():
        return 400, {'detail': 'Pipeline has deals'}
    Pipeline.objects.filter(id=pipeline_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/pipelines/{pipeline_id}/stages/')
def list_stages(request, pipeline_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    return [
        {'id': s.id, 'name': s.name, 'stage_type': s.stage_type, 'color': s.color, 'sort_order': s.sort_order, 'auto_action': s.auto_action}
        for s in Stage.objects.filter(pipeline_id=pipeline_id).order_by('sort_order', 'id')
    ]


@crm_router.post('/pipelines/{pipeline_id}/stages/')
def create_stage(request, pipeline_id: int, payload: StageIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    s = Stage.objects.create(pipeline_id=pipeline_id, **payload.dict())
    return {'id': s.id}


@crm_router.patch('/stages/{stage_id}/')
def patch_stage(request, stage_id: int, payload: StagePatchIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    Stage.objects.filter(id=stage_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@crm_router.delete('/stages/{stage_id}/')
def delete_stage(request, stage_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    if Deal.objects.filter(stage_id=stage_id).exists():
        return 400, {'detail': 'Stage has deals'}
    Stage.objects.filter(id=stage_id).delete()
    return {'detail': 'deleted'}


@crm_router.post('/pipelines/{pipeline_id}/stages/reorder/')
def reorder_stages(request, pipeline_id: int, payload: list[int]):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    for index, stage_id in enumerate(payload):
        Stage.objects.filter(id=stage_id, pipeline_id=pipeline_id).update(sort_order=index)
    return {'detail': 'ok'}


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
    notify(tenant, 'new_deal_created', {'deal_id': deal.id, 'link': f'/crm'})
    return {'id': deal.id}


@crm_router.get('/deals/{deal_id}/')
def get_deal(request, deal_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    d = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='view')
    activities = Activity.objects.filter(deal_id=deal_id).order_by('-created_at')[:100]
    from apps.contracts.models import Contract, SigningSession
    from apps.channels.models import ChatSession as ChannelChatSession
    deal_contracts = list(Contract.objects.filter(deal=d).order_by('-created_at'))
    session_map = {}
    if deal_contracts:
        for s in SigningSession.objects.filter(contract__in=deal_contracts).order_by('contract_id', '-otp_sent_at'):
            if s.contract_id not in session_map:
                session_map[s.contract_id] = s.token
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
        'contracts': [
            {'id': c.id, 'template_name': c.template.name if c.template else None, 'status': c.status, 'created_at': c.created_at.isoformat(), 'contact_phone': d.contact.phone if d.contact else '', 'signing_url': f'{base_url}/sign/{session_map[c.id]}/' if c.id in session_map else None}
            for c in deal_contracts
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
    notify(tenant, 'deal_stage_changed', {'deal_id': deal.id, 'link': f'/crm'})
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


@crm_router.get('/contacts/{contact_id}/activities/')
def contact_activities(request, contact_id: int):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='view')
    return _serialize_activities(Activity.objects.filter(contact_id=contact_id).order_by('-created_at'))


@crm_router.get('/activities/tasks/')
def my_tasks(request, status: str | None = None):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    qs = Activity.objects.filter(activity_type='task', responsible_id=request.auth.id).order_by('due_date', '-created_at')
    if status:
        qs = qs.filter(status=status)
    return _serialize_activities(qs)


@crm_router.post('/activities/')
def create_activity(request, payload: ActivityIn):
    _ensure_builtin(request)
    if payload.deal_id:
        deal = _scoped_object_or_error(request, Deal, payload.deal_id, entity='deals', action='update')
    elif payload.contact_id:
        _scoped_object_or_error(request, Contact, payload.contact_id, entity='contacts', action='update')
        deal = None
    else:
        require_roles(request, ['owner', 'admin', 'manager'])
        deal = None

    activity = Activity.objects.create(
        activity_type=payload.activity_type,
        deal_id=payload.deal_id,
        contact_id=payload.contact_id,
        responsible_id=payload.responsible_id,
        title=payload.title,
        body=payload.body,
        status=payload.status,
        due_date=payload.due_date,
        created_by=request.auth if request.auth else (deal.responsible if deal else None),
    )
    return {'id': activity.id}


@crm_router.patch('/activities/{activity_id}/')
def patch_activity(request, activity_id: int, payload: ActivityPatchIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    _ensure_builtin(request)
    Activity.objects.filter(id=activity_id).update(**payload.dict(exclude_unset=True))
    return {'detail': 'ok'}


@crm_router.delete('/activities/{activity_id}/')
def delete_activity(request, activity_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    Activity.objects.filter(id=activity_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/stats/pipeline/{pipeline_id}/')
def pipeline_stats(request, pipeline_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    stats = (
        filter_crm_queryset_by_scope(request, Deal.objects.filter(pipeline_id=pipeline_id), 'deals')
        .values('stage_id', 'stage__name')
        .annotate(total=Count('id'), amount=Sum('amount'))
        .order_by('stage__name')
    )
    return [{'stage_id': s['stage_id'], 'stage_name': s['stage__name'], 'total': s['total'], 'amount': float(s['amount'] or 0)} for s in stats]


@crm_router.get('/stats/managers/')
def manager_stats(request):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    stats = (
        filter_crm_queryset_by_scope(request, Deal.objects.all(), 'deals')
        .values('responsible_id', 'responsible__first_name', 'responsible__last_name', 'responsible__email')
        .annotate(total=Count('id'), amount=Sum('amount'))
        .order_by('-total')
    )
    result = []
    for row in stats:
        name = f"{row['responsible__first_name'] or ''} {row['responsible__last_name'] or ''}".strip()
        if not name:
            name = row['responsible__email'] or '—'
        result.append({
            'responsible_id': row['responsible_id'],
            'manager_name': name,
            'total': row['total'],
            'amount': float(row['amount'] or 0),
        })
    return result


def _serialize_activities(qs):
    return [
        {
            'id': a.id,
            'activity_type': a.activity_type,
            'deal_id': a.deal_id,
            'contact_id': a.contact_id,
            'responsible_id': a.responsible_id,
            'title': a.title,
            'body': a.body,
            'status': a.status,
            'due_date': a.due_date.isoformat() if a.due_date else None,
            'created_at': a.created_at.isoformat(),
        }
        for a in qs
    ]
