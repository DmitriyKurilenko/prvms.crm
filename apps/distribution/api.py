from __future__ import annotations

from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth

from apps.core.access import require_feature_access, require_roles
from .models import DistributionLog, DistributionRule

distribution_router = Router(tags=['distribution'], auth=JWTAuth())


class DistributionRuleIn(Schema):
    name: str
    crm_connection_id: int | None = None
    trigger: str
    trigger_filter: dict = {}
    strategy: str = 'min_load'
    strategy_config: dict = {}
    managers: list[int] = []
    fallback_manager_id: int | None = None
    is_active: bool = True
    priority: int = 0


class DistributionRulePatchIn(Schema):
    name: str | None = None
    crm_connection_id: int | None = None
    trigger: str | None = None
    trigger_filter: dict | None = None
    strategy: str | None = None
    strategy_config: dict | None = None
    managers: list[int] | None = None
    fallback_manager_id: int | None = None
    is_active: bool | None = None
    priority: int | None = None


@distribution_router.get('/rules/')
def list_rules(request):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'distribution')
    rules = DistributionRule.objects.all().order_by('-priority', 'id')
    return [
        {
            'id': rule.id,
            'name': rule.name,
            'crm_connection_id': rule.crm_connection_id,
            'trigger': rule.trigger,
            'trigger_filter': rule.trigger_filter,
            'strategy': rule.strategy,
            'strategy_config': rule.strategy_config,
            'managers': list(rule.managers.values_list('id', flat=True)),
            'fallback_manager_id': rule.fallback_manager_id,
            'is_active': rule.is_active,
            'priority': rule.priority,
        }
        for rule in rules
    ]


@distribution_router.post('/rules/')
def create_rule(request, payload: DistributionRuleIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'distribution')
    rule = DistributionRule.objects.create(
        name=payload.name,
        crm_connection_id=payload.crm_connection_id,
        trigger=payload.trigger,
        trigger_filter=payload.trigger_filter,
        strategy=payload.strategy,
        strategy_config=payload.strategy_config,
        fallback_manager_id=payload.fallback_manager_id,
        is_active=payload.is_active,
        priority=payload.priority,
    )
    if payload.managers:
        rule.managers.set(payload.managers)
    return {'id': rule.id}


@distribution_router.patch('/rules/{rule_id}/')
def patch_rule(request, rule_id: int, payload: DistributionRulePatchIn):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'distribution')
    rule = DistributionRule.objects.get(id=rule_id)
    for key, value in payload.dict(exclude_unset=True).items():
        if key == 'managers':
            rule.managers.set(value)
            continue
        setattr(rule, key, value)
    rule.save()
    return {'detail': 'ok'}


@distribution_router.delete('/rules/{rule_id}/')
def delete_rule(request, rule_id: int):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'distribution')
    DistributionRule.objects.filter(id=rule_id).delete()
    return {'detail': 'deleted'}


@distribution_router.get('/log/')
def list_distribution_log(request, limit: int = 100, offset: int = 0):
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'distribution')
    qs = DistributionLog.objects.select_related('assigned_to', 'rule').order_by('-created_at')[offset : offset + limit]
    items = list(qs)

    # Resolve entity names for deals/leads
    deal_ids = [item.crm_entity_id for item in items if item.crm_entity_type in ('deal', 'lead')]
    deal_names: dict[str, str] = {}
    if deal_ids:
        from apps.crm.models import Deal
        for d in Deal.objects.filter(id__in=[int(x) for x in deal_ids if x.isdigit()]).only('id', 'name'):
            deal_names[str(d.id)] = d.name

    return [
        {
            'id': item.id,
            'rule_id': item.rule_id,
            'rule_name': item.rule.name if item.rule_id else None,
            'crm_entity_type': item.crm_entity_type,
            'crm_entity_id': item.crm_entity_id,
            'entity_name': deal_names.get(item.crm_entity_id) if item.crm_entity_type in ('deal', 'lead') else None,
            'assigned_to_id': item.assigned_to_id,
            'assigned_to_name': item.assigned_to.crm_user_name if item.assigned_to_id else None,
            'source': item.source,
            'strategy_used': item.strategy_used,
            'reason': item.reason,
            'created_at': item.created_at.isoformat(),
        }
        for item in items
    ]


@distribution_router.get('/managers/')
def list_available_managers(request):
    """List ManagerProfiles available for distribution rules."""
    require_roles(request, ['owner', 'admin'])
    require_feature_access(request, 'distribution')
    from .services import ensure_builtin_manager_profiles
    ensure_builtin_manager_profiles()
    from apps.integrations.models import ManagerProfile
    managers = ManagerProfile.objects.filter(is_active=True).select_related('user')
    return [
        {'id': m.id, 'name': m.crm_user_name or m.user.get_full_name() or m.user.email}
        for m in managers
    ]
