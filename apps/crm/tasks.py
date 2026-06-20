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
