"""Authentication, registration, invite acceptance, and tenant switching."""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django_tenants.utils import schema_context
from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

from apps.billing.models import Plan
from apps.core.access import get_crm_permissions, require_membership
from apps.core.tenant import get_request_tenant
from apps.tenants.models import Domain, Tenant
from apps.tenants.services import provision_tenant

from .models import Membership, User

auth_router = Router(tags=['auth'], auth=None)

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


class SwitchTenantIn(Schema):
    tenant_slug: str


# ---------- Endpoints ----------

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
            provision_tenant(tenant)

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
    except TokenError:
        return 400, {'detail': 'Invalid refresh token'}

    access = str(refresh.access_token)
    if settings.NINJA_JWT.get('ROTATE_REFRESH_TOKENS', False):
        if settings.NINJA_JWT.get('BLACKLIST_AFTER_ROTATION', False):
            try:
                refresh.blacklist()
            except TokenError:
                # Already blacklisted or rotated — proceed with new token issuance.
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
        except TokenError:
            # Token was already invalid/blacklisted — logout still succeeds.
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
            active_joined_memberships_queryset()
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
            active_joined_memberships_queryset()
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


# ---------- Internal helpers (re-used by team_api) ----------

def _set_refresh_cookie(response, refresh_token: str):
    secure = not settings.DEBUG
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite='None',
        max_age=7 * 24 * 60 * 60,
        path='/api/auth/',
    )


def _default_tenant_slug_for_user(user_id: int | None) -> str | None:
    if not user_id:
        return None
    with schema_context('public'):
        membership = (
            active_joined_memberships_queryset()
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


def active_joined_memberships_queryset():
    return Membership.objects.select_related('tenant').filter(
        is_active=True,
        tenant__is_active=True,
        invite_token__isnull=True,
        joined_at__isnull=False,
    )


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


def _user_has_login_password(user: User) -> bool:
    # Legacy safety: users created via `get_or_create` without password
    # can have empty-string password in DB, which is not a valid login password.
    return bool(user.password) and user.has_usable_password()


def build_invite_link(token: uuid.UUID | str) -> str:
    return f'{settings.FRONTEND_APP_URL.rstrip("/")}/invite/accept?token={token}'


def next_available_username(seed: str) -> str:
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
