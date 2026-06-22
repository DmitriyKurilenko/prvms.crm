from __future__ import annotations

from ninja.errors import HttpError

from apps.audit.services import log_event
from apps.core.access import require_roles

from ._api_common import _ensure_builtin, crm_router
from .models import AutomationRule
from .schemas import AutomationRuleIn, AutomationRulePatchIn

# Триггеры и типы действий, поддержанные исполнителем (`auto_actions.execute_action`).
_TRIGGERS = {'new_deal', 'stage_changed', 'no_activity'}
_ACTION_TYPES = {'create_task', 'send_notification', 'create_document', 'change_stage', 'assign'}


def _serialize(r: AutomationRule) -> dict:
    return {
        'id': r.id, 'name': r.name, 'trigger': r.trigger,
        'conditions': r.conditions, 'action': r.action,
        'is_active': r.is_active, 'priority': r.priority,
        'created_at': r.created_at.isoformat(),
    }


def _validate(trigger: str, action: dict) -> None:
    if trigger not in _TRIGGERS:
        raise HttpError(400, f'Недопустимый триггер: {trigger}')
    action_type = (action or {}).get('type')
    if action_type and action_type not in _ACTION_TYPES:
        raise HttpError(400, f'Недопустимое действие: {action_type}')


@crm_router.get('/automation/rules/')
def list_rules(request):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    return [_serialize(r) for r in AutomationRule.objects.all()]


@crm_router.post('/automation/rules/')
def create_rule(request, payload: AutomationRuleIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    _validate(payload.trigger, payload.action)
    rule = AutomationRule.objects.create(**payload.dict())
    log_event(request, action='create', instance=rule)
    return {'id': rule.id}


@crm_router.patch('/automation/rules/{rule_id}/')
def patch_rule(request, rule_id: int, payload: AutomationRulePatchIn):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    rule = AutomationRule.objects.filter(id=rule_id).first()
    if rule is None:
        raise HttpError(404, 'Not found')
    changes = payload.dict(exclude_unset=True)
    if 'trigger' in changes or 'action' in changes:
        _validate(changes.get('trigger', rule.trigger), changes.get('action', rule.action))
    if changes:
        AutomationRule.objects.filter(id=rule_id).update(**changes)
        log_event(request, action='update', instance=rule)
    return {'detail': 'ok'}


@crm_router.delete('/automation/rules/{rule_id}/')
def delete_rule(request, rule_id: int):
    require_roles(request, ['owner', 'admin'])
    _ensure_builtin(request)
    rule = AutomationRule.objects.filter(id=rule_id).first()
    if rule is None:
        raise HttpError(404, 'Not found')
    log_event(request, action='delete', instance=rule)
    AutomationRule.objects.filter(id=rule_id).delete()
    return {'detail': 'deleted'}
