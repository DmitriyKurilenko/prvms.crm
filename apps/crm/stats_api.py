from __future__ import annotations

from django.db.models import Count, Sum

from apps.core.access import (
    filter_crm_queryset_by_scope,
    require_crm_permission,
    require_roles,
)
from apps.core.tenant import get_request_tenant
from apps.users.models import Membership

from ._api_common import _ensure_builtin, crm_router
from .models import Deal


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
