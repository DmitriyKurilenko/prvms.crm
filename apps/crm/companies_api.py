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
    crm_router,
)
from .models import Company
from .schemas import CompanyIn, CompanyPatchIn


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
