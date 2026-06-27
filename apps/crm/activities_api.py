from __future__ import annotations

from ninja.errors import HttpError

from apps.core.access import get_membership, require_crm_permission, require_roles

from ._api_common import (
    _ensure_builtin,
    _scoped_object_or_error,
    _serialize_activities,
    crm_router,
)
from .models import Activity, Contact, Deal
from .schemas import ActivityIn, ActivityPatchIn
from .services.recurrence import next_occurrence


@crm_router.get('/activities/tasks/')
def my_tasks(request, status: str | None = None):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    qs = Activity.objects.filter(activity_type='task', responsible_id=request.auth.id).order_by('due_date', '-created_at')
    if status:
        qs = qs.filter(status=status)
    return _serialize_activities(qs)


@crm_router.get('/activities/calendar/')
def calendar_activities(request, date_from: str, date_to: str, scope: str = 'mine'):
    """Задачи с `due_date` в диапазоне [date_from, date_to] — источник для календаря.

    `scope='mine'` (по умолчанию) — только задачи текущего пользователя.
    `scope='team'`/`'all'` — все задачи тенанта; доступно только владельцу/админу,
    иначе тихо откатывается на личные задачи. В командном виде добавляется
    `responsible_name` для подписи событий.
    """
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    qs = Activity.objects.filter(
        activity_type='task',
        due_date__date__gte=date_from,
        due_date__date__lte=date_to,
    ).select_related('responsible').order_by('due_date')

    membership = get_membership(request)
    allow_team = membership is not None and membership.role in ('owner', 'admin')
    if scope in ('team', 'all') and allow_team:
        rows = list(qs)
    else:
        rows = list(qs.filter(responsible_id=request.auth.id))

    data = _serialize_activities(rows)
    name_by_id = {
        a.id: ((a.responsible.get_full_name() or a.responsible.email) if a.responsible else '')
        for a in rows
    }
    for item in data:
        item['responsible_name'] = name_by_id.get(item['id'], '')
    return data


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
        recurrence_rule=payload.recurrence_rule or '',
        remind_at=payload.remind_at,
        created_by=request.auth if request.auth else (deal.responsible if deal else None),
    )
    return {'id': activity.id}


@crm_router.patch('/activities/{activity_id}/')
def patch_activity(request, activity_id: int, payload: ActivityPatchIn):
    require_roles(request, ['owner', 'admin', 'manager'])
    _ensure_builtin(request)
    activity = Activity.objects.filter(id=activity_id).first()
    if activity is None:
        raise HttpError(404, 'Not found')

    changes = payload.dict(exclude_unset=True)
    was_done = activity.status == 'done'
    Activity.objects.filter(id=activity_id).update(**changes)

    # Повторяющаяся задача: при закрытии порождаем следующий экземпляр серии.
    becomes_done = changes.get('status') == 'done' and not was_done
    spawned_id = None
    if becomes_done:
        activity.refresh_from_db()
        nxt_due = next_occurrence(activity.due_date, activity.recurrence_rule)
        if nxt_due is not None:
            new_remind = None
            if activity.remind_at and activity.due_date:
                new_remind = activity.remind_at + (nxt_due - activity.due_date)
            spawned = Activity.objects.create(
                activity_type='task',
                deal_id=activity.deal_id,
                contact_id=activity.contact_id,
                responsible_id=activity.responsible_id,
                title=activity.title,
                body=activity.body,
                status='planned',
                due_date=nxt_due,
                recurrence_rule=activity.recurrence_rule,
                remind_at=new_remind,
                created_by=activity.created_by,
            )
            spawned_id = spawned.id
    return {'detail': 'ok', 'spawned_id': spawned_id}


@crm_router.delete('/activities/{activity_id}/')
def delete_activity(request, activity_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    Activity.objects.filter(id=activity_id).delete()
    return {'detail': 'deleted'}
