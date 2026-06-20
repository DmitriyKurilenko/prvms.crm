from __future__ import annotations

import logging

from django.db import transaction

from apps.integrations.adapters import get_adapter, get_adapter_for_tenant
from apps.integrations.models import ManagerProfile
from apps.notifications.services import notify

from .models import DistributionLog, DistributionRule
from .strategies import STRATEGIES

logger = logging.getLogger(__name__)


def ensure_builtin_manager_profiles() -> None:
    """Sync ManagerProfiles from Memberships for builtin-CRM tenants.

    Creates missing profiles, updates names, deactivates removed members.
    """
    from django.db import connection as db_connection

    from apps.users.models import Membership

    tenant = db_connection.tenant
    if getattr(tenant, 'crm_mode', None) != 'builtin':
        return

    memberships = (
        Membership.objects.filter(tenant=tenant, is_active=True)
        .exclude(role='viewer')
        .select_related('user')
    )
    active_user_ids = set()
    for m in memberships:
        active_user_ids.add(m.user_id)
        name = m.user.get_full_name() or m.user.email
        ManagerProfile.objects.update_or_create(
            user=m.user,
            crm_connection=None,
            defaults={
                'crm_user_id': str(m.user_id),
                'crm_user_name': name,
                'is_active': True,
            },
        )
    # Deactivate profiles for users no longer in active memberships
    if active_user_ids:
        ManagerProfile.objects.filter(
            crm_connection=None,
        ).exclude(user_id__in=active_user_ids).update(is_active=False)


def choose_rule(trigger: str, payload: dict) -> DistributionRule | None:
    rules = DistributionRule.objects.filter(trigger=trigger, is_active=True).order_by('-priority', 'id')
    for rule in rules:
        if _match_filter(rule.trigger_filter, payload):
            return rule
    return None


def assign_entity(rule: DistributionRule, entity_type: str, entity_id: str, source: str, payload: dict) -> DistributionLog:
    from django.db import connection

    candidates = list(rule.managers.filter(is_active=True))
    # If no specific managers assigned — use all active ManagerProfiles in tenant
    if not candidates:
        candidates = list(ManagerProfile.objects.filter(is_active=True))

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
            crm_connection=rule.crm_connection,
            crm_entity_type=entity_type,
            crm_entity_id=entity_id,
            assigned_to=manager,
            source=source,
            strategy_used=rule.strategy,
            reason=reason,
        )

    if manager and manager.crm_user_id:
        try:
            adapter = get_adapter(rule.crm_connection) if rule.crm_connection else get_adapter_for_tenant(connection.tenant)
            adapter.set_responsible(entity_type, entity_id, str(manager.crm_user_id))
        except Exception as exc:  # noqa: BLE001
            log.reason = f'{log.reason}; crm_assign_error={exc}'
            log.save(update_fields=['reason'])

        tenant = connection.tenant
        notify(
            tenant,
            'lead_distributed',
            {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'manager_name': manager.crm_user_name,
                'link': '/distribution',
                'message': f'Сущность {entity_type}:{entity_id} назначена менеджеру {manager.crm_user_name}.',
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
