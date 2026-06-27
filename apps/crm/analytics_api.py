"""Аналитика воронки и планы продаж (Фаза 10, DEC-055).

Отчёты строятся ORM-агрегированием поверх `Deal` со scope-фильтром
(`filter_crm_queryset_by_scope`), как в `stats_api.py`. Планы продаж
(`SalesTarget`) задаются по менеджеру на месяц; факт — выигранные сделки с
`closed_at` в пределах месяца (поле проставляется в `move_deal`).
"""
from __future__ import annotations

from datetime import date, datetime

from django.db.models import Count, Sum
from ninja.errors import HttpError

from apps.audit.services import log_event
from apps.core.access import (
    filter_crm_queryset_by_scope,
    require_crm_permission,
    require_roles,
)

from ._api_common import _ensure_builtin, crm_router
from .models import Deal, SalesTarget, Stage
from .schemas import SalesTargetIn, SalesTargetPatchIn


def _month_bounds(period: str) -> tuple[date, date]:
    """'YYYY-MM' → (первое число месяца, первое число следующего месяца)."""
    try:
        start = datetime.strptime(f'{period}-01', '%Y-%m-%d').date()
    except (ValueError, TypeError) as exc:
        raise HttpError(400, 'Период должен быть в формате YYYY-MM') from exc
    nxt = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, nxt


def _manager_name(row: dict, prefix: str = 'responsible') -> str:
    name = f"{row.get(f'{prefix}__first_name') or ''} {row.get(f'{prefix}__last_name') or ''}".strip()
    return name or row.get(f'{prefix}__email') or '—'


# --- Аналитика воронки -------------------------------------------------------

@crm_router.get('/analytics/funnel/')
def funnel(request, pipeline_id: int, date_from: str | None = None, date_to: str | None = None):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    deals = filter_crm_queryset_by_scope(request, Deal.objects.filter(pipeline_id=pipeline_id), 'deals')
    if date_from:
        deals = deals.filter(created_at__date__gte=date_from)
    if date_to:
        deals = deals.filter(created_at__date__lte=date_to)

    total = deals.count()
    by_stage = {
        row['stage_id']: row
        for row in deals.values('stage_id').annotate(count=Count('id'), amount=Sum('amount'))
    }

    # Честный исторический проход: сколько уникальных сделок из этой когорты
    # когда-либо входило в каждую стадию (по логу StageTransition). Достоверно
    # только с момента внедрения лога — для старых сделок переходов нет.
    from .models import StageTransition
    deal_ids = list(deals.values_list('id', flat=True))
    reached_by_stage = {
        row['to_stage_id']: row['c']
        for row in (
            StageTransition.objects.filter(deal_id__in=deal_ids)
            .values('to_stage_id')
            .annotate(c=Count('deal_id', distinct=True))
        )
    }
    history_since = (
        StageTransition.objects.filter(deal_id__in=deal_ids)
        .order_by('created_at')
        .values_list('created_at', flat=True)
        .first()
    )

    stages = []
    prev_reached = None
    for st in Stage.objects.filter(pipeline_id=pipeline_id).order_by('sort_order'):
        row = by_stage.get(st.id, {})
        count = row.get('count', 0)
        reached = reached_by_stage.get(st.id, 0)
        # Поэтапная конверсия = доля дошедших до этой стадии от предыдущей.
        if prev_reached is None:
            reached_conversion = 100.0 if reached else 0.0
        else:
            reached_conversion = round(reached / prev_reached * 100, 1) if prev_reached else 0.0
        prev_reached = reached
        stages.append({
            'stage_id': st.id,
            'stage_name': st.name,
            'stage_type': st.stage_type,
            'count': count,
            'amount': float(row.get('amount') or 0),
            'share': round(count / total * 100, 1) if total else 0.0,
            'reached': reached,
            'reached_conversion': reached_conversion,
        })
    won = deals.filter(stage__stage_type='won').count()
    lost = deals.filter(stage__stage_type='lost').count()
    open_count = deals.filter(stage__stage_type='open').count()
    win_rate = round(won / (won + lost) * 100, 1) if (won + lost) else 0.0
    return {
        'stages': stages,
        'summary': {'total': total, 'won': won, 'lost': lost, 'open': open_count, 'win_rate': win_rate},
        'history_since': history_since.isoformat() if history_since else None,
    }


@crm_router.get('/analytics/loss-reasons/')
def loss_reasons(request, date_from: str | None = None, date_to: str | None = None):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    lost = filter_crm_queryset_by_scope(request, Deal.objects.filter(stage__stage_type='lost'), 'deals')
    if date_from:
        lost = lost.filter(closed_at__date__gte=date_from)
    if date_to:
        lost = lost.filter(closed_at__date__lte=date_to)
    grouped = lost.values('loss_reason').annotate(count=Count('id'), amount=Sum('amount')).order_by('-count')
    return [
        {
            'loss_reason': row['loss_reason'] or 'Не указана',
            'count': row['count'],
            'amount': float(row['amount'] or 0),
        }
        for row in grouped
    ]


@crm_router.get('/analytics/forecast/')
def forecast(request, date_from: str | None = None, date_to: str | None = None):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    open_deals = filter_crm_queryset_by_scope(request, Deal.objects.filter(stage__stage_type='open'), 'deals')
    open_agg = open_deals.aggregate(amount=Sum('amount'), count=Count('id'))
    period = open_deals
    if date_from:
        period = period.filter(expected_close_date__gte=date_from)
    if date_to:
        period = period.filter(expected_close_date__lte=date_to)
    period_agg = period.aggregate(amount=Sum('amount'), count=Count('id'))
    return {
        'open_total_amount': float(open_agg['amount'] or 0),
        'open_count': open_agg['count'] or 0,
        'period_forecast_amount': float(period_agg['amount'] or 0),
        'period_forecast_count': period_agg['count'] or 0,
    }


# --- Планы продаж ------------------------------------------------------------

@crm_router.get('/targets/')
def list_targets(request, period: str | None = None):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    qs = SalesTarget.objects.select_related('responsible', 'pipeline').order_by('-period_month')
    if period:
        start, _ = _month_bounds(period)
        qs = qs.filter(period_month=start)
    return [
        {
            'id': t.id,
            'period': t.period_month.strftime('%Y-%m'),
            'responsible_id': t.responsible_id,
            'manager_name': (t.responsible.get_full_name() or t.responsible.email) if t.responsible else 'Команда',
            'pipeline_id': t.pipeline_id,
            'pipeline_name': t.pipeline.name if t.pipeline else 'Все воронки',
            'target_amount': float(t.target_amount) if t.target_amount is not None else None,
            'target_count': t.target_count,
        }
        for t in qs
    ]


@crm_router.post('/targets/')
def upsert_target(request, payload: SalesTargetIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    start, _ = _month_bounds(payload.period)
    target, _created = SalesTarget.objects.update_or_create(
        period_month=start,
        responsible_id=payload.responsible_id,
        pipeline_id=payload.pipeline_id,
        defaults={'target_amount': payload.target_amount, 'target_count': payload.target_count},
    )
    log_event(request, action='update', instance=target,
              changes={'План': {'before': '', 'after': f'{payload.period} amount={payload.target_amount} count={payload.target_count}'}})
    return {'id': target.id}


@crm_router.patch('/targets/{target_id}/')
def patch_target(request, target_id: int, payload: SalesTargetPatchIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    changes = payload.dict(exclude_unset=True)
    SalesTarget.objects.filter(id=target_id).update(**changes)
    return {'detail': 'ok'}


@crm_router.delete('/targets/{target_id}/')
def delete_target(request, target_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    SalesTarget.objects.filter(id=target_id).delete()
    return {'detail': 'deleted'}


@crm_router.get('/analytics/target-progress/')
def target_progress(request, period: str):
    """План против факта по каждому менеджеру за месяц. Факт — выигранные сделки
    с `closed_at` в пределах месяца."""
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    start, nxt = _month_bounds(period)

    won_base = Deal.objects.filter(
        stage__stage_type='won', closed_at__date__gte=start, closed_at__date__lt=nxt,
    )

    rows = []
    targets = SalesTarget.objects.filter(period_month=start).select_related('responsible', 'pipeline')
    targeted_mgr_ids = set()
    for t in targets:
        scoped = won_base
        if t.responsible_id:
            scoped = scoped.filter(responsible_id=t.responsible_id)
            targeted_mgr_ids.add(t.responsible_id)
        if t.pipeline_id:
            scoped = scoped.filter(pipeline_id=t.pipeline_id)
        agg = scoped.aggregate(actual_amount=Sum('amount'), actual_count=Count('id'))
        actual_amount = float(agg['actual_amount'] or 0)
        actual_count = agg['actual_count'] or 0
        target_amount = float(t.target_amount) if t.target_amount is not None else None
        target_count = t.target_count
        if t.responsible_id:
            name = t.responsible.get_full_name() or t.responsible.email
        else:
            name = 'Команда'
        if t.pipeline_id:
            name = f'{name} · {t.pipeline.name}'
        rows.append({
            'responsible_id': t.responsible_id,
            'pipeline_id': t.pipeline_id,
            'manager_name': name,
            'target_amount': target_amount,
            'actual_amount': actual_amount,
            'amount_pct': round(actual_amount / target_amount * 100, 1) if target_amount else None,
            'target_count': target_count,
            'actual_count': actual_count,
            'count_pct': round(actual_count / target_count * 100, 1) if target_count else None,
        })

    # Менеджеры с фактом, но без единого плана на месяц — показываем факт без плана.
    extra = (
        won_base.exclude(responsible_id__in=targeted_mgr_ids)
        .values('responsible_id', 'responsible__first_name', 'responsible__last_name', 'responsible__email')
        .annotate(actual_amount=Sum('amount'), actual_count=Count('id'))
    )
    for row in extra:
        rows.append({
            'responsible_id': row['responsible_id'],
            'pipeline_id': None,
            'manager_name': _manager_name(row),
            'target_amount': None,
            'actual_amount': float(row['actual_amount'] or 0),
            'amount_pct': None,
            'target_count': None,
            'actual_count': row['actual_count'] or 0,
            'count_pct': None,
        })
    rows.sort(key=lambda r: r['actual_amount'], reverse=True)
    return rows
