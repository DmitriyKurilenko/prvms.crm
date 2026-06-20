from __future__ import annotations

from datetime import datetime, time

from django.db.models import Avg, Count
from django.utils import timezone
from django.utils.dateparse import parse_date
from django_tenants.utils import schema_context
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_feature_access, require_roles
from apps.core.tenant import get_request_tenant
from apps.distribution.models import DistributionLog
from apps.documents.models import Document
from apps.notifications.presence import list_online_user_ids
from apps.telephony.models import CallRecord
from apps.users.models import Membership

from .models import Deal

dashboard_router = Router(tags=['dashboard'], auth=JWTAuth())


@dashboard_router.get('/stats/')
def stats(request, date_from: str | None = None, date_to: str | None = None):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    start, end = _date_range(date_from, date_to)
    document_qs = Document.objects.all()
    distribution_qs = DistributionLog.objects.all()
    calls_qs = CallRecord.objects.all()
    deals_qs = Deal.objects.all()
    if start:
        document_qs = document_qs.filter(created_at__gte=start)
        distribution_qs = distribution_qs.filter(created_at__gte=start)
        calls_qs = calls_qs.filter(started_at__gte=start)
        deals_qs = deals_qs.filter(updated_at__gte=start)
    if end:
        document_qs = document_qs.filter(created_at__lte=end)
        distribution_qs = distribution_qs.filter(created_at__lte=end)
        calls_qs = calls_qs.filter(started_at__lte=end)
        deals_qs = deals_qs.filter(updated_at__lte=end)

    today = timezone.localdate()
    return {
        'deals_open': deals_qs.filter(stage__stage_type='open').count(),
        'deals_won': deals_qs.filter(stage__stage_type='won').count(),
        'documents_total': document_qs.count(),
        'documents_signed': document_qs.filter(status='signed').count(),
        'distribution_today': DistributionLog.objects.filter(created_at__date=today).count(),
        'distribution_total': distribution_qs.count(),
        'calls_total': calls_qs.count(),
        'calls_missed': calls_qs.filter(result='missed').count(),
    }


@dashboard_router.get('/managers/')
def managers(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    deals_qs = (
        Deal.objects.values('responsible_id', 'responsible__first_name', 'responsible__last_name', 'responsible__email')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    calls_qs = (
        CallRecord.objects.values('manager_id', 'manager__crm_user_name')
        .annotate(total_calls=Count('id'), avg_duration=Avg('duration'))
        .order_by('-total_calls')
    )
    won_by_manager = {
        row['responsible_id']: row['won_total']
        for row in Deal.objects.filter(stage__stage_type='won').values('responsible_id').annotate(won_total=Count('id'))
    }
    deal_rows = []
    for row in deals_qs:
        manager_id = row['responsible_id']
        total = row['total'] or 0
        won = won_by_manager.get(manager_id, 0)
        win_rate = (won / total * 100) if total else 0
        name = f"{row['responsible__first_name'] or ''} {row['responsible__last_name'] or ''}".strip()
        if not name:
            name = row['responsible__email'] or '—'
        deal_rows.append({
            'responsible_id': manager_id,
            'responsible__crm_user_name': name,
            'total': total,
            'won': won,
            'win_rate': round(win_rate, 2),
        })
    return {'deals': deal_rows, 'calls': list(calls_qs)}


MANAGER_ROLES = ('owner', 'admin', 'manager')


@dashboard_router.get('/managers-online/')
def managers_online(request):
    require_roles(request, ['owner', 'admin', 'manager'])
    require_feature_access(request, 'analytics')
    tenant = get_request_tenant(request)
    online_user_ids = list_online_user_ids(tenant.schema_name)
    with schema_context('public'):
        member_ids = set(
            Membership.objects.filter(
                tenant_id=tenant.id,
                is_active=True,
                joined_at__isnull=False,
                invite_token__isnull=True,
                role__in=MANAGER_ROLES,
            ).values_list('user_id', flat=True)
        )
    online = sorted(online_user_ids.intersection(member_ids))
    return {
        'online': len(online),
        'total': len(member_ids),
        'user_ids': online,
    }


def _date_range(date_from: str | None, date_to: str | None):
    start = parse_date(date_from) if date_from else None
    end = parse_date(date_to) if date_to else None
    start_dt = timezone.make_aware(datetime.combine(start, time.min)) if start else None
    end_dt = timezone.make_aware(datetime.combine(end, time.max)) if end else None
    return start_dt, end_dt
