from __future__ import annotations

from django.conf import settings
from django.db import connection
from django_tenants.utils import schema_context
from ninja.errors import HttpError

from apps.tenants.models import Domain, Tenant


LOCAL_HOST_ALIASES = {'localhost', '127.0.0.1', '::1'}


def get_request_tenant(request, required: bool = True):
    """
    Resolve tenant for current request in a robust way.

    Resolution order:
    1) request.tenant (if already set by django-tenants middleware)
    2) Explicit hint via X-Tenant-Slug header / query / cookie
    3) Host/domain lookup in shared schema
    4) DEBUG fallback: single active tenant in system
    """
    tenant = getattr(request, 'tenant', None)
    if tenant and getattr(tenant, 'schema_name', None) != 'public':
        return tenant

    tenant = _resolve_tenant_fallback(request)
    if tenant:
        request.tenant = tenant
        connection.set_tenant(tenant)
        return tenant

    if required:
        raise HttpError(
            400,
            'Tenant context is required. Use tenant domain or pass X-Tenant-Slug header.',
        )
    return None


def _resolve_tenant_fallback(request):
    tenant_slug = _tenant_slug_hint(request)
    host = _request_host(request)

    with schema_context('public'):
        if tenant_slug:
            tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
            if tenant:
                return tenant

        if host:
            domain = Domain.objects.select_related('tenant').filter(domain=host, tenant__is_active=True).first()
            if domain:
                return domain.tenant

        if settings.DEBUG:
            # Developer-friendly fallback for localhost-only setups.
            active = list(Tenant.objects.filter(is_active=True).order_by('id')[:2])
            if len(active) == 1:
                return active[0]
    return None


def _tenant_slug_hint(request) -> str:
    headers = getattr(request, 'headers', {})
    slug = (
        headers.get('X-Tenant-Slug')
        or request.META.get('HTTP_X_TENANT_SLUG')
        or request.GET.get('tenant_slug')
        or request.GET.get('tenant')
        or request.COOKIES.get('tenant_slug')
        or ''
    )
    slug = str(slug).strip().lower()
    if slug:
        return slug

    host = _request_host(request)
    if host.endswith('.localhost'):
        return host.split('.', 1)[0]
    return ''


def _request_host(request) -> str:
    raw = ''
    try:
        raw = request.get_host()
    except Exception:  # noqa: BLE001
        raw = request.META.get('HTTP_HOST', '')
    host = str(raw).split(':', 1)[0].strip().lower()
    if host in LOCAL_HOST_ALIASES:
        return host
    return host
