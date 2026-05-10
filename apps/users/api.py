import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django_tenants.utils import schema_context
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken

from apps.billing.models import Plan
from apps.audit.services import log_event
from apps.notifications.services import seed_default_preferences
from apps.core.access import get_crm_permissions, require_membership, require_roles
from apps.core.tenant import get_request_tenant
from apps.tenants.models import Tenant, Domain
from .permissions import (
    ALLOWED_MEMBERSHIP_ROLES,
    CRM_PERMISSION_ENTITIES,
    CRM_PERMISSION_SCOPES,
    get_role_permissions_matrix,
    update_role_permission,
)
from .models import User, Membership

auth_router = Router(tags=['auth'], auth=None)
users_router = Router(tags=['users'], auth=JWTAuth())

INVITE_TTL = timedelta(hours=48)


# ---------- Schemas ----------

class LoginIn(Schema):
    login: str | None = None
    email: str | None = None
    username: str | None = None
    password: str


class TokenOut(Schema):
    access_token: str
    tenant_slug: str | None = None


class RegisterIn(Schema):
    email: str
    password: str
    username: str
    org_name: str
    org_slug: str
    plan_slug: str = 'simple'


class RegisterOut(Schema):
    access_token: str
    tenant_slug: str


class InviteAcceptIn(Schema):
    token: str
    password: str = ''
    username: str = ''


class UserOut(Schema):
    id: int
    email: str
    username: str
    role: str | None = None
    status: str | None = None
    invite_link: str | None = None


class MeOut(Schema):
    id: int
    email: str
    username: str
    role: str
    tenant_id: int
    tenant_name: str
    tenant_slug: str
    crm_permissions: dict


class OrganizationOut(Schema):
    tenant_id: int
    tenant_slug: str
    tenant_name: str
    role: str
    joined_at: str | None = None


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


class SwitchTenantIn(Schema):
    tenant_slug: str


class ManagerPatchIn(Schema):
    max_active_deals: int | None = None
    schedule: dict | None = None


class DayOffIn(Schema):
    date: str
    reason: str = ''


# ---------- Auth endpoints ----------

@auth_router.post('/login', response={200: TokenOut, 401: dict})
def login(request, payload: LoginIn):
    auth_username = _resolve_auth_username(payload)
    if not auth_username:
        return 401, {'detail': 'Invalid credentials'}

    user = authenticate(request, username=auth_username, password=payload.password)
    if user is None:
        return 401, {'detail': 'Invalid credentials'}
    tenant_slug = _default_tenant_slug_for_user(user.id)
    refresh = RefreshToken.for_user(user)
    response = JsonResponse({'access_token': str(refresh.access_token), 'tenant_slug': tenant_slug})
    _set_refresh_cookie(response, str(refresh))
    return response


@auth_router.post('/register', response={201: RegisterOut, 400: dict})
def register(request, payload: RegisterIn):
    with schema_context('public'):
        if User.objects.filter(email=payload.email).exists():
            return 400, {'detail': 'Email already registered'}
        if Tenant.objects.filter(slug=payload.org_slug).exists():
            return 400, {'detail': 'Organization slug already taken'}

        plan = Plan.objects.filter(slug=payload.plan_slug, is_active=True).first()
        if not plan:
            return 400, {'detail': f'Plan "{payload.plan_slug}" not found'}

        with transaction.atomic():
            user = User.objects.create_user(
                email=payload.email,
                username=payload.username,
                password=payload.password,
            )
            tenant = Tenant.objects.create(
                name=payload.org_name,
                slug=payload.org_slug,
                schema_name=payload.org_slug,
                plan=plan,
                trial_expires_at=timezone.now() + timedelta(days=7),
                is_paid=False,
            )
            Domain.objects.create(
                domain=f'{payload.org_slug}.localhost',
                tenant=tenant,
                is_primary=True,
            )
            Membership.objects.create(
                user=user,
                tenant=tenant,
                role='owner',
                joined_at=timezone.now(),
            )
            with schema_context(tenant.schema_name):
                seed_default_preferences()

    refresh = RefreshToken.for_user(user)
    response = JsonResponse(
        {
            'access_token': str(refresh.access_token),
            'tenant_slug': tenant.slug,
        },
        status=201,
    )
    _set_refresh_cookie(response, str(refresh))
    return response


@auth_router.post('/refresh', response={200: TokenOut, 400: dict})
def refresh_token(request):
    raw = request.COOKIES.get('refresh_token')
    if not raw:
        return 400, {'detail': 'Missing refresh token'}
    try:
        refresh = RefreshToken(raw)
    except Exception:
        return 400, {'detail': 'Invalid refresh token'}

    access = str(refresh.access_token)
    if settings.NINJA_JWT.get('ROTATE_REFRESH_TOKENS', False):
        if settings.NINJA_JWT.get('BLACKLIST_AFTER_ROTATION', False):
            try:
                refresh.blacklist()
            except Exception:
                pass
        user = User.objects.get(id=refresh['user_id'])
        new_refresh = RefreshToken.for_user(user)
        response = JsonResponse(
            {
                'access_token': str(new_refresh.access_token),
                'tenant_slug': _default_tenant_slug_for_user(user.id),
            }
        )
        _set_refresh_cookie(response, str(new_refresh))
        return response
    user_id = refresh.get('user_id')
    return {'access_token': access, 'tenant_slug': _default_tenant_slug_for_user(user_id) if user_id else None}


@auth_router.get('/invite/check', response={200: dict, 400: dict})
def check_invite(request, token: str):
    membership = _get_pending_invite_membership(token)

    if not membership:
        return 400, {'detail': 'Недействительный токен приглашения'}

    if _invite_is_expired(membership):
        return 400, {'detail': 'Срок действия приглашения истёк'}

    return {
        'email': membership.user.email,
        'org_name': membership.tenant.name,
        'role': membership.role,
        'has_account': _user_has_login_password(membership.user),
    }


@auth_router.post('/invite/accept', response={200: TokenOut, 400: dict})
def accept_invite(request, payload: InviteAcceptIn):
    membership = _get_pending_invite_membership(payload.token)

    if not membership:
        return 400, {'detail': 'Недействительный токен приглашения'}

    if _invite_is_expired(membership):
        return 400, {'detail': 'Срок действия приглашения истёк'}

    user = membership.user
    with transaction.atomic():
        if _user_has_login_password(user):
            if not payload.password:
                return 400, {'detail': 'Введите пароль существующего аккаунта для принятия приглашения'}
            authenticated = authenticate(request, username=user.email, password=payload.password)
            if not authenticated or authenticated.id != user.id:
                return 400, {'detail': 'Неверный пароль'}
        else:
            if not payload.password:
                return 400, {'detail': 'Пароль обязателен для нового пользователя'}
            username = (payload.username or '').strip()
            if username:
                with schema_context('public'):
                    username_taken = User.objects.exclude(id=user.id).filter(username__iexact=username).exists()
                if username_taken:
                    return 400, {'detail': 'Username already taken'}
                user.username = username
            user.set_password(payload.password)
            user.save(update_fields=['username', 'password'])

        membership.invite_token = None
        membership.invited_at = None
        membership.joined_at = timezone.now()
        membership.save(update_fields=['invite_token', 'invited_at', 'joined_at'])

    refresh = RefreshToken.for_user(user)
    response = JsonResponse({
        'access_token': str(refresh.access_token),
        'tenant_slug': membership.tenant.slug,
    })
    _set_refresh_cookie(response, str(refresh))
    return response


@auth_router.post('/logout')
def logout(request):
    raw = request.COOKIES.get('refresh_token')
    if raw:
        try:
            RefreshToken(raw).blacklist()
        except Exception:
            pass
    response = JsonResponse({'detail': 'Logged out'})
    response.delete_cookie('refresh_token')
    return response


@auth_router.get('/me', response=MeOut, auth=JWTAuth())
def me(request):
    user = request.auth
    tenant = get_request_tenant(request)
    membership = require_membership(request, check_trial=False)
    crm_permissions = get_crm_permissions(request, check_trial=False)
    return MeOut(
        id=user.id,
        email=user.email,
        username=user.username,
        role=membership.role,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        crm_permissions=crm_permissions,
    )


@auth_router.get('/organizations', response=list[OrganizationOut], auth=JWTAuth())
def list_organizations(request):
    with schema_context('public'):
        memberships = list(
            _active_joined_memberships_queryset()
            .filter(user_id=request.auth.id)
            .order_by('-joined_at', 'id')
        )
    return [
        OrganizationOut(
            tenant_id=membership.tenant_id,
            tenant_slug=membership.tenant.slug,
            tenant_name=membership.tenant.name,
            role=membership.role,
            joined_at=membership.joined_at.isoformat() if membership.joined_at else None,
        )
        for membership in memberships
    ]


@auth_router.post('/switch-tenant', response={200: TokenOut, 403: dict}, auth=JWTAuth())
def switch_tenant(request, payload: SwitchTenantIn):
    slug = str(payload.tenant_slug or '').strip().lower()
    if not slug:
        return 403, {'detail': 'Недостаточно прав для доступа к этой организации'}

    with schema_context('public'):
        membership = (
            _active_joined_memberships_queryset()
            .filter(user_id=request.auth.id, tenant__slug=slug)
            .first()
        )

    if not membership:
        return 403, {'detail': 'Недостаточно прав для доступа к этой организации'}

    refresh = RefreshToken.for_user(request.auth)
    response = JsonResponse({
        'access_token': str(refresh.access_token),
        'tenant_slug': membership.tenant.slug,
    })
    _set_refresh_cookie(response, str(refresh))
    return response


def _set_refresh_cookie(response, refresh_token: str):
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='None',
        max_age=7 * 24 * 60 * 60,
        path='/api/auth/',
    )


def _default_tenant_slug_for_user(user_id: int | None) -> str | None:
    if not user_id:
        return None
    with schema_context('public'):
        membership = (
            _active_joined_memberships_queryset()
            .filter(user_id=user_id)
            .order_by('-joined_at', 'id')
            .first()
        )
    if not membership:
        return None
    return membership.tenant.slug


def _resolve_auth_username(payload: LoginIn) -> str | None:
    candidates = (payload.login, payload.email, payload.username)
    raw = next((str(value).strip() for value in candidates if value and str(value).strip()), '')
    if not raw:
        return None

    with schema_context('public'):
        user = User.objects.filter(email__iexact=raw).only('email').first()
        if user:
            return user.email
        user = User.objects.filter(username__iexact=raw).only('email').first()
        if user:
            return user.email

    if '@' in raw:
        return raw.lower()
    return raw


# ---------- Users management endpoints ----------

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
        elif m.joined_at:
            status = 'active'
            link = None
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
                username = _next_available_username(email.split('@', 1)[0] or 'user')
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

    invite_link = _build_invite_link(token)
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
    # If pending invite — fully remove membership
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

    # Refresh token and timestamp
    membership.invite_token = uuid.uuid4()
    membership.invited_at = timezone.now()
    membership.save(update_fields=['invite_token', 'invited_at'])

    invite_link = _build_invite_link(membership.invite_token)
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


def _active_joined_memberships_queryset():
    return Membership.objects.select_related('tenant').filter(
        is_active=True,
        tenant__is_active=True,
        invite_token__isnull=True,
        joined_at__isnull=False,
    )


def _normalize_membership_role(role: str | None) -> str | None:
    normalized = str(role or '').strip().lower()
    if normalized not in ALLOWED_MEMBERSHIP_ROLES:
        return None
    return normalized


def _normalize_email(email: str | None) -> str:
    return str(email or '').strip().lower()


def _get_pending_invite_membership(token: str):
    with schema_context('public'):
        return (
            Membership.objects.filter(
                invite_token=token,
                is_active=True,
                tenant__is_active=True,
            )
            .select_related('user', 'tenant')
            .first()
        )


def _invite_is_expired(membership: Membership) -> bool:
    if not membership.invited_at:
        return False
    return timezone.now() - membership.invited_at > INVITE_TTL


def _build_invite_link(token: uuid.UUID | str) -> str:
    return f'{settings.FRONTEND_APP_URL.rstrip("/")}/invite/accept?token={token}'


def _user_has_login_password(user: User) -> bool:
    # Legacy safety: users created via `get_or_create` without password
    # can have empty-string password in DB, which is not a valid login password.
    return bool(user.password) and user.has_usable_password()


def _next_available_username(seed: str) -> str:
    base = ''.join(ch for ch in str(seed).strip().lower() if ch.isalnum() or ch in {'_', '-', '.'}) or 'user'
    base = base[:150]
    candidate = base
    suffix = 1
    with schema_context('public'):
        while User.objects.filter(username__iexact=candidate).exists():
            suffix_token = f'_{suffix}'
            candidate = f'{base[: max(1, 150 - len(suffix_token))]}{suffix_token}'
            suffix += 1
    return candidate


# ---------- Manager profiles ----------

@users_router.get('/managers/')
def list_manager_profiles(request):
    """List manager profiles with schedule and days-off for current tenant."""
    require_roles(request, ['owner', 'admin'])
    from apps.distribution.services import ensure_builtin_manager_profiles
    from apps.integrations.models import ManagerProfile
    ensure_builtin_manager_profiles()
    profiles = ManagerProfile.objects.filter(is_active=True).select_related('user').prefetch_related('days_off')
    return [
        {
            'id': p.id,
            'user_id': p.user_id,
            'name': p.crm_user_name or (p.user.get_full_name() if p.user_id else ''),
            'email': p.user.email if p.user_id else '',
            'max_active_deals': p.max_active_deals,
            'schedule': p.schedule or {},
            'days_off': [
                {'id': d.id, 'date': d.date.isoformat(), 'reason': d.reason}
                for d in p.days_off.order_by('date')
            ],
        }
        for p in profiles
    ]


@users_router.patch('/managers/{manager_id}/')
def patch_manager_profile(request, manager_id: int, payload: ManagerPatchIn):
    """Update manager schedule or max_active_deals."""
    require_roles(request, ['owner', 'admin'])
    from apps.integrations.models import ManagerProfile
    profile = ManagerProfile.objects.filter(id=manager_id, is_active=True).first()
    if not profile:
        return {'detail': 'not found'}
    data = payload.dict(exclude_unset=True)
    if 'max_active_deals' in data:
        profile.max_active_deals = data['max_active_deals']
    if 'schedule' in data:
        profile.schedule = data['schedule']
    profile.save(update_fields=[k for k in data])
    return {'detail': 'ok'}


@users_router.post('/managers/{manager_id}/days-off/')
def add_day_off(request, manager_id: int, payload: DayOffIn):
    """Add a day-off for a manager."""
    require_roles(request, ['owner', 'admin'])
    from datetime import date as date_type
    from apps.integrations.models import ManagerProfile, ManagerDayOff
    profile = ManagerProfile.objects.filter(id=manager_id, is_active=True).first()
    if not profile:
        return {'detail': 'not found'}
    try:
        d = date_type.fromisoformat(payload.date)
    except ValueError:
        return {'detail': 'invalid date format, use YYYY-MM-DD'}
    day_off = ManagerDayOff.objects.create(manager=profile, date=d, reason=payload.reason)
    return {'id': day_off.id, 'date': day_off.date.isoformat(), 'reason': day_off.reason}


@users_router.delete('/managers/days-off/{day_off_id}/')
def delete_day_off(request, day_off_id: int):
    """Remove a day-off entry."""
    require_roles(request, ['owner', 'admin'])
    from apps.integrations.models import ManagerDayOff
    ManagerDayOff.objects.filter(id=day_off_id).delete()
    return {'detail': 'deleted'}
