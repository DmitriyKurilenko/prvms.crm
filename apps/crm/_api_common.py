"""Shared router + helpers for the split `apps.crm.api` modules.

`crm_router` is defined here once; every domain module
(`contacts_api`, `companies_api`, `pipelines_api`, `deals_api`,
`activities_api`, `stats_api`) imports it and attaches its endpoints via
decorators. The thin `apps.crm.api` shim imports all domain modules for
their decorator side-effects and re-exports `crm_router` for
`config/api.py`.
"""
from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.core.access import (
    ensure_crm_object_scope,
    normalize_crm_responsible_for_write,
    require_feature_access,
)
from apps.core.tenant import get_request_tenant

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
