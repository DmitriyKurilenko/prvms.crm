"""Team management — invitations, role updates, role-permission matrix."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django_tenants.utils import schema_context
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth

from apps.audit.services import log_event
from apps.core.access import require_roles
from apps.core.tenant import get_request_tenant

from .auth_api import build_invite_link, next_available_username
from .models import Membership, User
from .permissions import (
    ALLOWED_MEMBERSHIP_ROLES,
    CRM_PERMISSION_ENTITIES,
    CRM_PERMISSION_SCOPES,
    get_role_permissions_matrix,
    update_role_permission,
)

users_router = Router(tags=['users'], auth=JWTAuth())


# ---------- Schemas ----------

class UserOut(Schema):
    id: int
    email: str
    username: str
    role: str | None = None
    status: str | None = None
    invite_link: str | None = None


class InviteIn(Schema):
    email: str
    role: str = 'manager'


class RoleUpdateIn(Schema):
    role: str


class RolePermissionPatchIn(Schema):
    can_view: bool | None = None
    can_create: bool | None = None
    can_update: bool | None = None
    can_delete: bool | None = None
    scope: str | None = None


# ---------- Endpoints ----------

@users_router.get('/', response=list[UserOut])
def list_users(request):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    memberships = Membership.objects.filter(
        tenant=tenant, is_active=True,
    ).select_related('user')
    frontend_url = getattr(settings, 'FRONTEND_APP_URL', '')
    result = []
    for m in memberships:
        if m.invite_token:
            status = 'pending'
            link = f'{frontend_url}/invite/accept?token={m.invite_token}'
        else:
            status = 'active'
            link = None
        result.append(UserOut(
            id=m.user.id,
            email=m.user.email,
            username=m.user.username,
            role=m.role,
            status=status,
            invite_link=link,
        ))
    return result


@users_router.post('/invite', response={201: dict, 400: dict})
def invite_user(request, payload: InviteIn):
    require_roles(request, ['owner', 'admin'])
    role = _normalize_membership_role(payload.role)
    if not role:
        return 400, {'detail': 'Недопустимая роль'}

    email = _normalize_email(payload.email)
    if not email:
        return 400, {'detail': 'Email обязателен'}

    tenant = get_request_tenant(request)
    token = uuid.uuid4()
    now = timezone.now()

    with schema_context('public'):
        existing_membership = (
            Membership.objects.select_related('user')
            .filter(tenant_id=tenant.id, user__email__iexact=email)
            .first()
        )

        if existing_membership and existing_membership.is_active and not existing_membership.invite_token:
            return 400, {'detail': 'User already a member of this organization'}

        if existing_membership:
            existing_membership.role = role
            existing_membership.is_active = True
            existing_membership.invite_token = token
            existing_membership.invited_at = now
            existing_membership.joined_at = None
            existing_membership.save(
                update_fields=['role', 'is_active', 'invite_token', 'invited_at', 'joined_at']
            )
            user = existing_membership.user
        else:
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                username = next_available_username(email.split('@', 1)[0] or 'user')
                user = User.objects.create_user(
                    email=email,
                    username=username,
                    password=None,
                )
            Membership.objects.create(
                user=user,
                tenant_id=tenant.id,
                role=role,
                invite_token=token,
                invited_at=now,
            )

    invite_link = build_invite_link(token)
    send_mail(
        subject='Приглашение в CRM Platform',
        message=(
            f'Вас пригласили в организацию "{tenant.name}" с ролью "{role}".\n'
            f'Ссылка для принятия приглашения: {invite_link}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    return 201, {'invite_token': str(token), 'invite_link': invite_link}


@users_router.patch('/{user_id}/role', response={200: dict, 400: dict, 404: dict})
def update_role(request, user_id: int, payload: RoleUpdateIn):
    require_roles(request, ['owner', 'admin'])
    role = _normalize_membership_role(payload.role)
    if not role:
        return 400, {'detail': 'Недопустимая роль'}
    tenant = get_request_tenant(request)
    membership = Membership.objects.filter(
        user_id=user_id, tenant=tenant
    ).first()
    if not membership:
        return 404, {'detail': 'User not found in this organization'}
    previous_role = membership.role
    membership.role = role
    membership.save(update_fields=['role'])
    if previous_role != role:
        log_event(
            request,
            action='update',
            model_name='Membership',
            object_id=str(membership.id),
            object_repr=f'{membership.user.email} ({tenant.slug})',
            changes={'role': {'before': previous_role, 'after': role}},
        )
    return {'detail': 'Role updated'}


@users_router.get('/role-permissions/', response=dict)
def list_role_permissions(request):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    return {
        'roles': get_role_permissions_matrix(tenant.id),
        'entities': list(CRM_PERMISSION_ENTITIES),
        'scopes': list(CRM_PERMISSION_SCOPES),
    }


@users_router.patch('/role-permissions/{role}/{entity}/', response={200: dict, 400: dict})
def patch_role_permission(request, role: str, entity: str, payload: RolePermissionPatchIn):
    require_roles(request, ['owner', 'admin'])
    normalized_role = _normalize_membership_role(role)
    if not normalized_role:
        return 400, {'detail': 'Недопустимая роль'}
    normalized_entity = str(entity or '').strip().lower()
    if normalized_entity not in CRM_PERMISSION_ENTITIES:
        return 400, {'detail': 'Недопустимая сущность'}

    changes = payload.dict(exclude_unset=True)
    if not changes:
        return {'detail': 'ok'}

    tenant = get_request_tenant(request)
    try:
        before, after = update_role_permission(
            tenant_id=tenant.id,
            role=normalized_role,
            entity=normalized_entity,
            updates=changes,
        )
    except ValueError as exc:
        return 400, {'detail': str(exc)}

    log_event(
        request,
        action='update',
        model_name='RolePermission',
        object_id=f'{tenant.id}:{normalized_role}:{normalized_entity}',
        object_repr=f'{tenant.slug}:{normalized_role}:{normalized_entity}',
        changes={'before': before, 'after': after},
    )
    return {'detail': 'ok', 'permission': after}


@users_router.delete('/{user_id}', response={200: dict, 404: dict})
def deactivate_user(request, user_id: int):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    membership = Membership.objects.filter(
        user_id=user_id, tenant=tenant, is_active=True,
    ).first()
    if not membership:
        return 404, {'detail': 'User not found in this organization'}
    if membership.invite_token:
        membership.delete()
        return {'detail': 'Invite cancelled'}
    membership.is_active = False
    membership.save(update_fields=['is_active'])
    return {'detail': 'User deactivated'}


@users_router.post('/{user_id}/resend-invite', response={200: dict, 400: dict, 404: dict})
def resend_invite(request, user_id: int):
    """Resend invite email with a fresh token and expiration."""
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    membership = Membership.objects.filter(
        user_id=user_id, tenant=tenant, is_active=True,
    ).select_related('user').first()
    if not membership:
        return 404, {'detail': 'User not found in this organization'}
    if not membership.invite_token:
        return 400, {'detail': 'Пользователь уже принял приглашение'}

    membership.invite_token = uuid.uuid4()
    membership.invited_at = timezone.now()
    membership.save(update_fields=['invite_token', 'invited_at'])

    invite_link = build_invite_link(membership.invite_token)
    send_mail(
        subject='Приглашение в CRM Platform (повторное)',
        message=(
            f'Вас пригласили в организацию "{tenant.name}" с ролью "{membership.role}".\n'
            f'Ссылка для принятия приглашения: {invite_link}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[membership.user.email],
        fail_silently=True,
    )
    return {'detail': 'Invite resent', 'invite_link': invite_link}


# ---------- Helpers ----------

def _normalize_membership_role(role: str | None) -> str | None:
    normalized = str(role or '').strip().lower()
    if normalized not in ALLOWED_MEMBERSHIP_ROLES:
        return None
    return normalized


def _normalize_email(email: str | None) -> str:
    return str(email or '').strip().lower()
