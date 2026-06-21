from __future__ import annotations

from collections.abc import Mapping

from django_tenants.utils import schema_context

from .models import Membership, RolePermission

CRM_PERMISSION_ENTITIES: tuple[str, ...] = ('deals', 'contacts', 'companies', 'products', 'webforms')
CRM_PERMISSION_SCOPES: tuple[str, ...] = ('all', 'team', 'own')
CRM_PERMISSION_ACTION_FIELDS: dict[str, str] = {
    'view': 'can_view',
    'create': 'can_create',
    'update': 'can_update',
    'delete': 'can_delete',
}

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, dict[str, object]]] = {
    'owner': {
        'deals': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'contacts': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'companies': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'products': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'webforms': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
    },
    'admin': {
        'deals': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'contacts': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'companies': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'products': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
        'webforms': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': True, 'scope': 'all'},
    },
    'manager': {
        'deals': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': False, 'scope': 'all'},
        'contacts': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': False, 'scope': 'all'},
        'companies': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': False, 'scope': 'all'},
        'products': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': False, 'scope': 'all'},
        'webforms': {'can_view': True, 'can_create': True, 'can_update': True, 'can_delete': False, 'scope': 'all'},
    },
    'viewer': {
        'deals': {'can_view': True, 'can_create': False, 'can_update': False, 'can_delete': False, 'scope': 'all'},
        'contacts': {'can_view': True, 'can_create': False, 'can_update': False, 'can_delete': False, 'scope': 'all'},
        'companies': {'can_view': True, 'can_create': False, 'can_update': False, 'can_delete': False, 'scope': 'all'},
        'products': {'can_view': True, 'can_create': False, 'can_update': False, 'can_delete': False, 'scope': 'all'},
        'webforms': {'can_view': True, 'can_create': False, 'can_update': False, 'can_delete': False, 'scope': 'all'},
    },
}

ALLOWED_MEMBERSHIP_ROLES: tuple[str, ...] = tuple(DEFAULT_ROLE_PERMISSIONS.keys())


def _default_row(role: str, entity: str) -> dict[str, object]:
    role_defaults = DEFAULT_ROLE_PERMISSIONS.get(role)
    if not role_defaults:
        raise ValueError('Недопустимая роль')
    entity_defaults = role_defaults.get(entity)
    if not entity_defaults:
        raise ValueError('Недопустимая сущность')
    return dict(entity_defaults)


def _serialize_row(row: RolePermission) -> dict[str, object]:
    return {
        'can_view': bool(row.can_view),
        'can_create': bool(row.can_create),
        'can_update': bool(row.can_update),
        'can_delete': bool(row.can_delete),
        'scope': row.scope,
    }


def ensure_role_permissions(tenant_id: int) -> None:
    with schema_context('public'):
        existing = set(
            RolePermission.objects.filter(tenant_id=tenant_id).values_list('role', 'entity')
        )
        to_create: list[RolePermission] = []
        for role in ALLOWED_MEMBERSHIP_ROLES:
            for entity in CRM_PERMISSION_ENTITIES:
                if (role, entity) in existing:
                    continue
                defaults = _default_row(role, entity)
                to_create.append(
                    RolePermission(
                        tenant_id=tenant_id,
                        role=role,
                        entity=entity,
                        can_view=bool(defaults['can_view']),
                        can_create=bool(defaults['can_create']),
                        can_update=bool(defaults['can_update']),
                        can_delete=bool(defaults['can_delete']),
                        scope=str(defaults['scope']),
                    )
                )
        if to_create:
            RolePermission.objects.bulk_create(to_create)


def get_role_permissions_matrix(tenant_id: int) -> dict[str, dict[str, dict[str, object]]]:
    ensure_role_permissions(tenant_id)
    matrix = {
        role: {entity: _default_row(role, entity) for entity in CRM_PERMISSION_ENTITIES}
        for role in ALLOWED_MEMBERSHIP_ROLES
    }
    with schema_context('public'):
        rows = RolePermission.objects.filter(tenant_id=tenant_id)
    for row in rows:
        matrix[row.role][row.entity] = _serialize_row(row)
    return matrix


def get_role_permissions_for_role(tenant_id: int, role: str) -> dict[str, dict[str, object]]:
    normalized_role = str(role or '').strip().lower()
    matrix = get_role_permissions_matrix(tenant_id)
    if normalized_role in matrix:
        return matrix[normalized_role]
    return {entity: _default_row('viewer', entity) for entity in CRM_PERMISSION_ENTITIES}


def _normalized_updates(current: dict[str, object], updates: Mapping[str, object]) -> dict[str, object]:
    next_data = {
        'can_view': bool(current.get('can_view', False)),
        'can_create': bool(current.get('can_create', False)),
        'can_update': bool(current.get('can_update', False)),
        'can_delete': bool(current.get('can_delete', False)),
        'scope': str(current.get('scope', 'all')),
    }

    for key in ('can_view', 'can_create', 'can_update', 'can_delete'):
        if key in updates and updates[key] is not None:
            next_data[key] = bool(updates[key])

    if 'scope' in updates and updates['scope'] is not None:
        scope = str(updates['scope']).strip().lower()
        if scope not in CRM_PERMISSION_SCOPES:
            raise ValueError('Недопустимая область видимости')
        next_data['scope'] = scope

    if next_data['can_create'] or next_data['can_update'] or next_data['can_delete']:
        next_data['can_view'] = True

    if not next_data['can_view']:
        next_data['can_create'] = False
        next_data['can_update'] = False
        next_data['can_delete'] = False

    return next_data


def update_role_permission(
    tenant_id: int,
    role: str,
    entity: str,
    updates: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    normalized_role = str(role or '').strip().lower()
    normalized_entity = str(entity or '').strip().lower()

    if normalized_role not in ALLOWED_MEMBERSHIP_ROLES:
        raise ValueError('Недопустимая роль')
    if normalized_entity not in CRM_PERMISSION_ENTITIES:
        raise ValueError('Недопустимая сущность')

    ensure_role_permissions(tenant_id)

    with schema_context('public'):
        row = RolePermission.objects.filter(
            tenant_id=tenant_id,
            role=normalized_role,
            entity=normalized_entity,
        ).first()

        if row is None:
            defaults = _default_row(normalized_role, normalized_entity)
            row = RolePermission.objects.create(
                tenant_id=tenant_id,
                role=normalized_role,
                entity=normalized_entity,
                can_view=bool(defaults['can_view']),
                can_create=bool(defaults['can_create']),
                can_update=bool(defaults['can_update']),
                can_delete=bool(defaults['can_delete']),
                scope=str(defaults['scope']),
            )

        before = _serialize_row(row)
        after = _normalized_updates(before, updates)

        row.can_view = bool(after['can_view'])
        row.can_create = bool(after['can_create'])
        row.can_update = bool(after['can_update'])
        row.can_delete = bool(after['can_delete'])
        row.scope = str(after['scope'])
        row.save(update_fields=['can_view', 'can_create', 'can_update', 'can_delete', 'scope'])

    return before, after


def get_team_member_user_ids(tenant_id: int) -> set[int]:
    with schema_context('public'):
        return set(
            Membership.objects.filter(
                tenant_id=tenant_id,
                is_active=True,
                invite_token__isnull=True,
                joined_at__isnull=False,
            )
            .exclude(role='viewer')
            .values_list('user_id', flat=True)
        )


def is_assignable_member(tenant_id: int, user_id: int) -> bool:
    with schema_context('public'):
        return Membership.objects.filter(
            tenant_id=tenant_id,
            user_id=user_id,
            is_active=True,
            invite_token__isnull=True,
            joined_at__isnull=False,
        ).exclude(role='viewer').exists()
