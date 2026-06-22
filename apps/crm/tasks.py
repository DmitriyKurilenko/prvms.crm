from __future__ import annotations

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.notifications.services import notify
from apps.tenants.models import Tenant

from .models import Activity, Deal
from .services.auto_actions import process_stage_change


@shared_task
def process_stage_auto_action(tenant_id: int, deal_id: int, old_stage_id: int, new_stage_id: int):
    with schema_context('public'):
        tenant = Tenant.objects.get(id=tenant_id)
    with tenant_context(tenant):
        deal = Deal.objects.select_related('stage').get(id=deal_id)
        old_stage = deal.pipeline.stages.get(id=old_stage_id)
        new_stage = deal.pipeline.stages.get(id=new_stage_id)
        process_stage_change(deal, old_stage, new_stage)
        return {'status': 'ok'}


@shared_task
def evaluate_time_rules():
    """Time-based автоматизация: «нет активности N дней». Идемпотентна через
    AutomationRunLog (unique rule+deal)."""
    from datetime import timedelta

    from .models import AutomationRule, AutomationRunLog
    from .services.auto_actions import _match_conditions, execute_action

    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    fired = 0
    for tenant in tenants:
        with tenant_context(tenant):
            rules = AutomationRule.objects.filter(trigger='no_activity', is_active=True)
            for rule in rules:
                days = int((rule.conditions or {}).get('days', 3))
                threshold = timezone.now() - timedelta(days=days)
                deals = Deal.objects.filter(stage__stage_type='open').exclude(automation_runs__rule=rule)
                for deal in deals:
                    last = Activity.objects.filter(deal=deal).order_by('-created_at').first()
                    last_at = last.created_at if last else deal.created_at
                    if last_at < threshold and _match_conditions(rule.conditions or {}, deal):
                        execute_action(rule.action or {}, deal)
                        AutomationRunLog.objects.get_or_create(rule=rule, deal=deal)
                        fired += 1
    return {'fired': fired}


@shared_task
def check_overdue_tasks():
    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    updated = 0
    for tenant in tenants:
        with tenant_context(tenant):
            tasks = Activity.objects.filter(
                activity_type='task',
                status='planned',
                due_date__lt=timezone.now(),
            )
            for task in tasks:
                task.status = 'overdue'
                task.save(update_fields=['status'])
                updated += 1
                if task.responsible and task.responsible.user_id:
                    notify(tenant, 'task_overdue', {'message': f'Задача просрочена: {task.title}'})
    return {'updated': updated}
