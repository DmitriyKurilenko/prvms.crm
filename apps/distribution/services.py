from __future__ import annotations

import logging

from django.db import transaction

from apps.notifications.services import notify
from apps.team.models import Manager

from .models import DistributionLog, DistributionRule
from .strategies import STRATEGIES

logger = logging.getLogger(__name__)


def choose_rule(trigger: str, payload: dict) -> DistributionRule | None:
    rules = DistributionRule.objects.filter(trigger=trigger, is_active=True).order_by('-priority', 'id')
    for rule in rules:
        if _match_filter(rule.trigger_filter, payload):
            return rule
    return None


def assign_entity(rule: DistributionRule, entity_type: str, entity_id: str, source: str, payload: dict) -> DistributionLog:
    from django.db import connection

    candidates = list(rule.managers.filter(is_active=True))
    # Если конкретные менеджеры не заданы — берём всех активных в тенанте.
    if not candidates:
        candidates = list(Manager.objects.filter(is_active=True))

    strategy_cls = STRATEGIES.get(rule.strategy)
    if strategy_cls is None:
        raise ValueError(f'Unknown strategy: {rule.strategy}')

    config = dict(rule.strategy_config or {})
    manager, reason = strategy_cls().choose_manager(candidates, {'payload': payload, 'rule': rule}, config)

    with transaction.atomic():
        if config != (rule.strategy_config or {}):
            rule.strategy_config = config
            rule.save(update_fields=['strategy_config'])

        if manager is None and rule.fallback_manager and rule.fallback_manager.is_active:
            manager = rule.fallback_manager
            reason = f'{reason}; fallback_manager'

        log = DistributionLog.objects.create(
            rule=rule,
            crm_entity_type=entity_type,
            crm_entity_id=entity_id,
            assigned_to=manager,
            source=source,
            strategy_used=rule.strategy,
            reason=reason,
        )

    if manager:
        from apps.crm.adapter import get_crm_adapter
        try:
            get_crm_adapter().set_responsible(entity_type, entity_id, str(manager.user_id))
        except Exception as exc:  # noqa: BLE001 — назначение не должно ронять распределение
            log.reason = f'{log.reason}; assign_error={exc}'
            log.save(update_fields=['reason'])

        notify(
            connection.tenant,
            'lead_distributed',
            {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'manager_name': manager.display_name,
                'link': '/distribution',
                'message': f'Сущность {entity_type}:{entity_id} назначена менеджеру {manager.display_name}.',
            },
        )

    return log


def try_distribute(trigger: str, entity_type: str, entity_id: str,
                   source: str = 'builtin_crm', payload: dict | None = None) -> DistributionLog | None:
    """Attempt to distribute an entity. Returns log if distributed, None otherwise.

    Tries the exact trigger first. Falls back to new_lead↔new_deal synonyms.
    """
    triggers_to_try = [trigger]
    if trigger == 'new_deal':
        triggers_to_try.append('new_lead')
    elif trigger == 'new_lead':
        triggers_to_try.append('new_deal')

    payload = payload or {}
    for t in triggers_to_try:
        rule = choose_rule(t, payload)
        if rule:
            try:
                return assign_entity(rule, entity_type, entity_id, source, payload)
            except Exception:
                logger.exception('Distribution failed for %s:%s trigger=%s', entity_type, entity_id, t)
                return None
    return None


def _match_filter(rule_filter: dict, payload: dict) -> bool:
    if not rule_filter:
        return True
    for key, expected in rule_filter.items():
        if payload.get(key) != expected:
            return False
    return True
