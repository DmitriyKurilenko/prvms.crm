"""Manager profile and day-off endpoints (extends team users_router)."""
from __future__ import annotations

from datetime import date as date_type

from ninja import Schema

from apps.core.access import require_roles

from .team_api import users_router  # extend the same router so URLs stay stable


class ManagerPatchIn(Schema):
    max_active_deals: int | None = None
    schedule: dict | None = None


class DayOffIn(Schema):
    date: str
    reason: str = ''


@users_router.get('/managers/')
def list_manager_profiles(request):
    """List manager profiles with schedule and days-off for current tenant."""
    require_roles(request, ['owner', 'admin'])
    from apps.distribution.services import ensure_builtin_manager_profiles
    from apps.integrations.models import ManagerProfile
    ensure_builtin_manager_profiles()
    profiles = ManagerProfile.objects.filter(is_active=True).select_related('user').prefetch_related('days_off')
    return [
        {
            'id': p.id,
            'user_id': p.user_id,
            'name': p.crm_user_name or (p.user.get_full_name() if p.user_id else ''),
            'email': p.user.email if p.user_id else '',
            'max_active_deals': p.max_active_deals,
            'schedule': p.schedule or {},
            'days_off': [
                {'id': d.id, 'date': d.date.isoformat(), 'reason': d.reason}
                for d in p.days_off.order_by('date')
            ],
        }
        for p in profiles
    ]


@users_router.patch('/managers/{manager_id}/')
def patch_manager_profile(request, manager_id: int, payload: ManagerPatchIn):
    """Update manager schedule or max_active_deals."""
    require_roles(request, ['owner', 'admin'])
    from apps.integrations.models import ManagerProfile
    profile = ManagerProfile.objects.filter(id=manager_id, is_active=True).first()
    if not profile:
        return {'detail': 'not found'}
    data = payload.dict(exclude_unset=True)
    if 'max_active_deals' in data:
        profile.max_active_deals = data['max_active_deals']
    if 'schedule' in data:
        profile.schedule = data['schedule']
    profile.save(update_fields=[k for k in data])
    return {'detail': 'ok'}


@users_router.post('/managers/{manager_id}/days-off/')
def add_day_off(request, manager_id: int, payload: DayOffIn):
    """Add a day-off for a manager."""
    require_roles(request, ['owner', 'admin'])
    from apps.integrations.models import ManagerDayOff, ManagerProfile
    profile = ManagerProfile.objects.filter(id=manager_id, is_active=True).first()
    if not profile:
        return {'detail': 'not found'}
    try:
        d = date_type.fromisoformat(payload.date)
    except ValueError:
        return {'detail': 'invalid date format, use YYYY-MM-DD'}
    day_off = ManagerDayOff.objects.create(manager=profile, date=d, reason=payload.reason)
    return {'id': day_off.id, 'date': day_off.date.isoformat(), 'reason': day_off.reason}


@users_router.delete('/managers/days-off/{day_off_id}/')
def delete_day_off(request, day_off_id: int):
    """Remove a day-off entry."""
    require_roles(request, ['owner', 'admin'])
    from apps.integrations.models import ManagerDayOff
    ManagerDayOff.objects.filter(id=day_off_id).delete()
    return {'detail': 'deleted'}
