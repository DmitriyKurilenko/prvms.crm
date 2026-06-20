from __future__ import annotations

import re
from zoneinfo import available_timezones

from ninja import File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja_jwt.authentication import JWTAuth

from apps.billing.catalog import get_active_plans_queryset, serialize_plan_for_client
from apps.billing.usage import get_plan_usage_for_tenant
from apps.core.access import require_membership, require_roles
from apps.core.tenant import get_request_tenant

tenant_router = Router(tags=['tenant'], auth=JWTAuth())


SUPPORTED_LANGUAGES = ('ru', 'en')
BRAND_COLOR_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
LOGO_ALLOWED_CONTENT_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp'}
LOGO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


class TenantOut(Schema):
    id: int
    name: str
    slug: str
    crm_mode: str
    brand_color: str
    timezone: str
    language: str
    logo_url: str | None
    onboarding_step: int
    is_active: bool
    is_paid: bool
    trial_active: bool
    trial_expired: bool
    trial_expires_at: str | None


class TenantSettingsIn(Schema):
    name: str | None = None
    brand_color: str | None = None
    timezone: str | None = None
    language: str | None = None


class PlanUsageOut(Schema):
    plan_name: str
    plan_slug: str
    features: list[str]
    max_managers: int | None
    max_documents_per_month: int | None
    max_crm_connections: int | None
    max_pipelines: int | None
    usage: dict


class LogoOut(Schema):
    logo_url: str | None


def _tenant_logo_url(request, tenant) -> str | None:
    if not tenant.logo:
        return None
    try:
        url = tenant.logo.url
    except ValueError:
        return None
    if url.startswith(('http://', 'https://')):
        return url
    return request.build_absolute_uri(url)


def _serialize_tenant(request, tenant) -> TenantOut:
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        crm_mode=tenant.crm_mode,
        brand_color=tenant.brand_color,
        timezone=tenant.timezone,
        language=tenant.language,
        logo_url=_tenant_logo_url(request, tenant),
        onboarding_step=tenant.onboarding_step,
        is_active=tenant.is_active,
        is_paid=tenant.is_paid,
        trial_active=tenant.trial_active,
        trial_expired=tenant.trial_expired,
        trial_expires_at=tenant.trial_expires_at.isoformat() if tenant.trial_expires_at else None,
    )


def _validate_settings_payload(payload: TenantSettingsIn) -> dict:
    data = payload.dict(exclude_unset=True)
    if 'brand_color' in data and data['brand_color'] is not None:
        color = str(data['brand_color']).strip()
        if not BRAND_COLOR_RE.match(color):
            raise HttpError(400, 'Некорректный цвет бренда. Ожидается HEX вида #RRGGBB.')
        data['brand_color'] = color
    if 'timezone' in data and data['timezone'] is not None:
        tz = str(data['timezone']).strip()
        if tz not in available_timezones():
            raise HttpError(400, 'Некорректная таймзона. Ожидается IANA-значение, например Europe/Moscow.')
        data['timezone'] = tz
    if 'language' in data and data['language'] is not None:
        lang = str(data['language']).strip().lower()
        if lang not in SUPPORTED_LANGUAGES:
            raise HttpError(400, f'Некорректный язык. Поддерживаются: {", ".join(SUPPORTED_LANGUAGES)}.')
        data['language'] = lang
    if 'name' in data and data['name'] is not None:
        name = str(data['name']).strip()
        if not name:
            raise HttpError(400, 'Название организации не может быть пустым.')
        data['name'] = name
    return data


@tenant_router.get('/', response=TenantOut)
def get_tenant(request):
    require_membership(request, allow_trial_expired=True)
    tenant = get_request_tenant(request)
    return _serialize_tenant(request, tenant)


@tenant_router.patch('/settings', response=TenantOut)
def update_tenant_settings(request, payload: TenantSettingsIn):
    require_roles(request, ['owner', 'admin'])
    tenant = get_request_tenant(request)
    data = _validate_settings_payload(payload)
    if data:
        for field, value in data.items():
            setattr(tenant, field, value)
        tenant.save(update_fields=list(data.keys()))
    return _serialize_tenant(request, tenant)


@tenant_router.post('/logo', response=LogoOut)
def upload_tenant_logo(request, file: UploadedFile = File(...)):
    require_roles(request, ['owner'])
    tenant = get_request_tenant(request)
    _validate_logo_file(file)
    if tenant.logo:
        tenant.logo.delete(save=False)
    tenant.logo.save(_build_logo_name(tenant, file), file, save=True)
    return LogoOut(logo_url=_tenant_logo_url(request, tenant))


@tenant_router.delete('/logo', response=LogoOut)
def delete_tenant_logo(request):
    require_roles(request, ['owner'])
    tenant = get_request_tenant(request)
    if tenant.logo:
        tenant.logo.delete(save=False)
        tenant.logo = ''
        tenant.save(update_fields=['logo'])
    return LogoOut(logo_url=None)


def _validate_logo_file(file: UploadedFile) -> None:
    content_type = (getattr(file, 'content_type', '') or '').lower()
    if content_type and content_type not in LOGO_ALLOWED_CONTENT_TYPES:
        raise HttpError(400, 'Неподдерживаемый формат файла. Разрешены PNG, JPEG, SVG, WEBP.')
    size = getattr(file, 'size', None)
    if size is not None and size > LOGO_MAX_BYTES:
        raise HttpError(400, 'Файл слишком большой. Максимум 2 МБ.')


def _build_logo_name(tenant, file: UploadedFile) -> str:
    name = getattr(file, 'name', 'logo') or 'logo'
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else 'png'
    if ext not in {'png', 'jpg', 'jpeg', 'svg', 'webp'}:
        ext = 'png'
    return f'{tenant.slug}.{ext}'


@tenant_router.get('/plan/', response=PlanUsageOut)
def get_plan(request):
    require_membership(request, allow_trial_expired=True)
    tenant = get_request_tenant(request)
    plan = tenant.plan
    features = list(plan.features.values_list('code', flat=True))
    usage = get_plan_usage_for_tenant(tenant)
    return PlanUsageOut(
        plan_name=plan.name,
        plan_slug=plan.slug,
        features=features,
        max_managers=plan.max_managers,
        max_documents_per_month=plan.max_documents_per_month,
        max_crm_connections=plan.max_crm_connections,
        max_pipelines=plan.max_pipelines,
        usage=usage,
    )


@tenant_router.get('/plans/')
def available_plans(request):
    require_membership(request, allow_trial_expired=True)
    plans = get_active_plans_queryset()
    return [serialize_plan_for_client(plan) for plan in plans]
