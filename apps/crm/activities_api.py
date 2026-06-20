from __future__ import annotations

from apps.core.access import require_crm_permission, require_roles

from ._api_common import (
    _ensure_builtin,
    _scoped_object_or_error,
    _serialize_activities,
    crm_router,
)
from .models import Activity, Contact, Deal
from .schemas import ActivityIn, ActivityPatchIn


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
