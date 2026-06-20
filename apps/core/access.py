from __future__ import annotations

from django.db.models import Q
from django_tenants.utils import schema_context
from ninja.errors import HttpError

from apps.users.models import Membership
from apps.users.permissions import (
    CRM_PERMISSION_ACTION_FIELDS,
    CRM_PERMISSION_ENTITIES,
    get_role_permissions_for_role,
    get_team_member_user_ids,
    is_assignable_member,
)

from .tenant import get_request_tenant


def _check_trial(tenant, *, allow_trial_expired: bool = False):
    """Raise 402 if tenant's trial has expired and no payment."""
    if tenant.trial_expired and not allow_trial_expired:
        raise HttpError(
            402,
            'Пробный период истёк. Оформите подписку для продолжения работы.',
        )


def get_membership(request):
    user = request.auth
    tenant = get_request_tenant(request, required=False)
    if user is None or tenant is None:
        return None
    with schema_context('public'):
        return Membership.objects.filter(user_id=user.id, tenant_id=tenant.id, is_active=True).first()


def require_membership(request, check_trial: bool = True, allow_trial_expired: bool = False):
    membership = get_membership(request)
    if not membership:
        raise HttpError(403, 'Forbidden: active membership is required for this tenant.')
    tenant = get_request_tenant(request, required=False)
    if check_trial and tenant:
        _check_trial(tenant, allow_trial_expired=allow_trial_expired)
    return membership


def require_roles(
    request,
    roles: list[str],
    *,
    check_trial: bool = True,
    allow_trial_expired: bool = False,
):
    membership = require_membership(request, check_trial=False)
    if membership.role not in roles:
        raise HttpError(403, f'Forbidden: required roles {roles}')
    if check_trial:
        tenant = get_request_tenant(request, required=False)
        if tenant:
            _check_trial(tenant, allow_trial_expired=allow_trial_expired)
    return membership


def require_feature_access(request, feature_code: str):
    tenant = get_request_tenant(request)
    _check_trial(tenant)
    if not tenant.plan.has_feature(feature_code):
        raise HttpError(403, f'Feature "{feature_code}" is not available for your plan.')


def _get_request_crm_permissions(request, *, check_trial: bool) -> tuple[Membership, dict[str, dict[str, object]]]:
    membership = require_membership(request, check_trial=check_trial)
    cache_attr = '_crm_permissions_cache'
    cached = getattr(request, cache_attr, None)
    if cached and cached.get('tenant_id') == membership.tenant_id and cached.get('role') == membership.role:
        return membership, cached['permissions']
    permissions = get_role_permissions_for_role(membership.tenant_id, membership.role)
    setattr(
        request,
        cache_attr,
        {'tenant_id': membership.tenant_id, 'role': membership.role, 'permissions': permissions},
    )
    return membership, permissions


def get_crm_permissions(request, *, check_trial: bool = False) -> dict[str, dict[str, object]]:
    _, permissions = _get_request_crm_permissions(request, check_trial=check_trial)
    return permissions


def require_crm_permission(request, entity: str, action: str, *, check_trial: bool = True) -> tuple[Membership, dict[str, object]]:
    normalized_entity = str(entity or '').strip().lower()
    normalized_action = str(action or '').strip().lower()
    if normalized_entity not in CRM_PERMISSION_ENTITIES:
        raise HttpError(500, f'Unknown CRM entity "{normalized_entity}"')
    action_field = CRM_PERMISSION_ACTION_FIELDS.get(normalized_action)
    if not action_field:
        raise HttpError(500, f'Unknown CRM action "{normalized_action}"')

    membership, permissions = _get_request_crm_permissions(request, check_trial=check_trial)
    entity_permissions = permissions.get(normalized_entity, {})
    if not bool(entity_permissions.get(action_field, False)):
        raise HttpError(403, f'Недостаточно прав: {normalized_entity}.{normalized_action}')
    return membership, entity_permissions


def _team_ids_for_membership(membership: Membership, request) -> set[int]:
    cache_attr = '_crm_team_ids_cache'
    cached = getattr(request, cache_attr, None)
    if cached and cached.get('tenant_id') == membership.tenant_id:
        return cached['user_ids']
    user_ids = get_team_member_user_ids(membership.tenant_id)
    setattr(request, cache_attr, {'tenant_id': membership.tenant_id, 'user_ids': user_ids})
    return user_ids


def _scope_q(scope: str, actor_id: int, team_ids: set[int] | None = None) -> Q:
    normalized_scope = str(scope or 'all').strip().lower()
    if normalized_scope == 'own':
        return Q(responsible_id=actor_id)
    if normalized_scope == 'team':
        team_ids = team_ids or set()
        return Q(responsible_id__isnull=True) | Q(responsible_id__in=team_ids)
    return Q()


def filter_crm_queryset_by_scope(request, queryset, entity: str):
    membership, entity_permissions = require_crm_permission(request, entity, 'view')
    scope = str(entity_permissions.get('scope', 'all'))
    if scope == 'all':
        return queryset
    if scope == 'own':
        return queryset.filter(responsible_id=request.auth.id)
    team_ids = _team_ids_for_membership(membership, request)
    return queryset.filter(_scope_q(scope, request.auth.id, team_ids))


def ensure_crm_object_scope(request, entity: str, action: str, obj) -> tuple[Membership, dict[str, object]]:
    membership, entity_permissions = require_crm_permission(request, entity, action)
    scope = str(entity_permissions.get('scope', 'all'))
    if scope == 'all':
        return membership, entity_permissions

    responsible_id = getattr(obj, 'responsible_id', None)
    if scope == 'own':
        if responsible_id != request.auth.id:
            raise HttpError(403, f'Недостаточно прав на {entity}.{action}')
        return membership, entity_permissions

    team_ids = _team_ids_for_membership(membership, request)
    if responsible_id is not None and responsible_id not in team_ids:
        raise HttpError(403, f'Недостаточно прав на {entity}.{action}')
    return membership, entity_permissions


def normalize_crm_responsible_for_write(
    request,
    entity: str,
    action: str,
    responsible_id: int | None,
    *,
    default_to_actor_on_own: bool = False,
) -> int | None:
    membership, entity_permissions = require_crm_permission(request, entity, action)
    scope = str(entity_permissions.get('scope', 'all'))
    normalized_responsible = int(responsible_id) if responsible_id is not None else None

    if normalized_responsible is not None and not is_assignable_member(membership.tenant_id, normalized_responsible):
        raise HttpError(400, 'Некорректный ответственный: пользователь не состоит в организации')

    if scope == 'all':
        return normalized_responsible

    if scope == 'team':
        if normalized_responsible is None:
            return None
        team_ids = _team_ids_for_membership(membership, request)
        if normalized_responsible not in team_ids:
            raise HttpError(403, f'Недостаточно прав на {entity}.{action}')
        return normalized_responsible

    if scope == 'own':
        if normalized_responsible is None:
            if default_to_actor_on_own:
                return request.auth.id
            raise HttpError(403, f'Недостаточно прав на {entity}.{action}')
        if normalized_responsible != request.auth.id:
            raise HttpError(403, f'Недостаточно прав на {entity}.{action}')
        return normalized_responsible

    return normalized_responsible
