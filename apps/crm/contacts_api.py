from __future__ import annotations

from django.db.models import Q

from apps.audit.services import log_event
from apps.core.access import (
    filter_crm_queryset_by_scope,
    normalize_crm_responsible_for_write,
    require_crm_permission,
)

from ._api_common import (
    _apply_responsible_write_guard,
    _ensure_builtin,
    _scoped_object_or_error,
    _serialize_activities,
    crm_router,
)
from .models import Activity, Contact
from .schemas import ContactIn, ContactPatchIn


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


@crm_router.get('/contacts/{contact_id}/activities/')
def contact_activities(request, contact_id: int):
    require_crm_permission(request, 'contacts', 'view')
    _ensure_builtin(request)
    _scoped_object_or_error(request, Contact, contact_id, entity='contacts', action='view')
    return _serialize_activities(Activity.objects.filter(contact_id=contact_id).order_by('-created_at'))
