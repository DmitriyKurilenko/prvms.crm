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
def import_records(schema_name: str, job_id: int, entity: str, rows: list[dict], mapping: dict):
    """Импорт контактов/компаний батчами с дедупом и построчным отчётом об ошибках.

    `mapping`: {column_name -> model_field}. Колонки, отображённые на поле не из
    набора `allowed_fields`, складываются в `custom_fields`. Дедуп: контакты — по
    телефону, затем email; компании — по ИНН, затем названию.
    """
    from .models import Company, Contact, ImportJob
    from .services.import_export import allowed_fields

    allowed = set(allowed_fields(entity))
    model = Contact if entity == 'contacts' else Company

    with schema_context(schema_name):
        job = ImportJob.objects.get(id=job_id)
        job.status, job.total = 'running', len(rows)
        job.save(update_fields=['status', 'total'])
        for i, raw in enumerate(rows):
            try:
                fields: dict = {}
                custom: dict = {}
                for column, target in mapping.items():
                    if not target:
                        continue
                    value = (raw.get(column) or '')
                    if isinstance(value, str):
                        value = value.strip()
                    if target in allowed:
                        fields[target] = value
                    else:
                        custom[target] = value
                _import_one(entity, model, fields, custom, job)
            except Exception as exc:  # noqa: BLE001 — построчная устойчивость импорта
                job.errors.append({'row': i + 2, 'message': str(exc)})
            job.processed = i + 1
            if (i + 1) % 50 == 0:
                job.save(update_fields=['processed', 'created', 'updated', 'errors'])
        job.status = 'done'
        job.save()
        return {'created': job.created, 'updated': job.updated, 'errors': len(job.errors)}


def _import_one(entity: str, model, fields: dict, custom: dict, job):
    """Создаёт или обновляет одну запись с дедупом. Бросает ValueError на пустой строке."""
    if entity == 'contacts':
        phone = fields.get('phone', '')
        email = fields.get('email', '')
        if not (fields.get('first_name') or phone or email):
            raise ValueError('Пустая строка: нет имени, телефона и email')
        dup = None
        if phone:
            dup = model.objects.filter(phone=phone).first()
        if dup is None and email:
            dup = model.objects.filter(email=email).first()
    else:  # companies
        name = fields.get('name', '')
        inn = fields.get('inn', '')
        if not (name or inn):
            raise ValueError('Пустая строка: нет названия и ИНН')
        dup = None
        if inn:
            dup = model.objects.filter(inn=inn).first()
        if dup is None and name:
            dup = model.objects.filter(name=name).first()

    if dup is not None:
        changed = False
        for key, value in fields.items():
            if value and getattr(dup, key, None) != value:
                setattr(dup, key, value)
                changed = True
        if custom:
            merged = dict(dup.custom_fields or {})
            merged.update(custom)
            dup.custom_fields = merged
            changed = True
        if changed:
            dup.save()
        job.updated += 1
    else:
        model.objects.create(custom_fields=custom or {}, **fields)
        job.created += 1


@shared_task
def send_task_reminders():
    """Заблаговременные напоминания о задачах. Идемпотентна через `reminder_sent_at`:
    одно напоминание на задачу. Адресат — ответственный за задачу (`notify_user`)."""
    from apps.notifications.services import notify_user

    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))
    sent = 0
    now = timezone.now()
    for tenant in tenants:
        with tenant_context(tenant):
            due = Activity.objects.filter(
                activity_type='task',
                status='planned',
                remind_at__isnull=False,
                remind_at__lte=now,
                reminder_sent_at__isnull=True,
            ).select_related('responsible')
            for task in due:
                if task.responsible_id:
                    link = f'/app/deals/{task.deal_id}' if task.deal_id else '/app/calendar'
                    notify_user(tenant, task.responsible, 'task_reminder',
                                {'message': f'Напоминание о задаче: {task.title}', 'link': link})
                task.reminder_sent_at = now
                task.save(update_fields=['reminder_sent_at'])
                sent += 1
    return {'sent': sent}


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
