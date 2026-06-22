from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.crm.models import Activity, Deal, Stage
from apps.documents.models import DocumentTemplate
from apps.documents.services import create_document_from_deal
from apps.notifications.services import notify


def execute_action(action: dict, deal: Deal) -> None:
    """Единая точка исполнения действия. Используется и stage-auto-action,
    и правилами автоматизации (`AutomationRule`)."""
    action_type = action.get('type')
    if not action_type:
        return

    if action_type == 'create_document':
        template = DocumentTemplate.objects.get(id=action['template_id'])
        create_document_from_deal(deal, template)
        return

    if action_type == 'send_notification':
        from django.db import connection

        notify(
            connection.tenant,
            action.get('event', 'deal_stage_changed'),
            {'deal_id': deal.id, 'link': f'/crm/deals/{deal.id}'},
        )
        return

    if action_type == 'create_task':
        Activity.objects.create(
            activity_type='task',
            deal=deal,
            responsible=deal.responsible,
            title=action.get('title', 'Новая задача'),
            status='planned',
            due_date=timezone.now() + timedelta(days=int(action.get('days_offset', 1))),
            created_by=deal.responsible,
        )
        return

    if action_type == 'change_stage':
        new_stage = Stage.objects.get(id=action['stage_id'], pipeline_id=deal.pipeline_id)
        deal.stage = new_stage
        deal.save(update_fields=['stage'])
        return

    if action_type == 'assign':
        deal.responsible_id = action['responsible_id']
        deal.save(update_fields=['responsible'])
        return


def process_stage_change(deal: Deal, old_stage: Stage, new_stage: Stage):
    """Executes configured stage action after deal movement (обёртка над execute_action)."""
    action = new_stage.auto_action or {}
    if action.get('type'):
        execute_action(action, deal)


def _match_conditions(conditions: dict, deal: Deal) -> bool:
    if conditions.get('pipeline_id') and conditions['pipeline_id'] != deal.pipeline_id:
        return False
    if conditions.get('stage_id') and conditions['stage_id'] != deal.stage_id:
        return False
    return True


def evaluate_event_rules(event: str, deal: Deal) -> int:
    """Исполняет активные правила-триггеры данного события для сделки.

    Не вызывается рекурсивно из `execute_action` — события возбуждаются только
    из API-эндпоинтов (`create_deal`/`move_deal`), поэтому циклов нет.
    """
    from apps.crm.models import AutomationRule

    fired = 0
    rules = AutomationRule.objects.filter(trigger=event, is_active=True).order_by('-priority', 'id')
    for rule in rules:
        if _match_conditions(rule.conditions or {}, deal):
            execute_action(rule.action or {}, deal)
            fired += 1
    return fired
