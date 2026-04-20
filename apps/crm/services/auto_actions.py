from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.contracts.models import ContractTemplate
from apps.contracts.services import create_contract_from_deal
from apps.notifications.services import notify
from apps.crm.models import Activity, Deal, Stage


def process_stage_change(deal: Deal, old_stage: Stage, new_stage: Stage):
    """Executes configured stage action after deal movement."""
    action = new_stage.auto_action or {}
    action_type = action.get('type')
    if not action_type:
        return

    if action_type == 'create_contract':
        template = ContractTemplate.objects.get(id=action['template_id'])
        create_contract_from_deal(deal, template)
        return

    if action_type == 'send_notification':
        from django.db import connection as connection

        notify(connection.tenant, action.get('event', 'deal_stage_changed'), {'deal_id': deal.id, 'link': f'/crm/deals/{deal.id}'})
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
