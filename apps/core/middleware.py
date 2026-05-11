from __future__ import annotations

from django.http import JsonResponse
from django.utils import translation

from .tenant import get_request_tenant


SUPPORTED_LANGUAGES = ('ru', 'en')

# Paths that must respond before tenant resolution. Liveness/readiness probes
# from container orchestrators (Docker healthcheck, k8s, load balancers) hit
# the backend with Host: localhost / 127.0.0.1, which TenantMainMiddleware
# cannot resolve to a Domain row and therefore returns 404 for. Answering
# /healthz here keeps the probe independent of Domain/Tenant state.
HEALTHZ_PATHS = frozenset({'/healthz', '/healthz/'})


class HealthCheckBypassMiddleware:
    """Respond to /healthz before any tenant/auth/security middleware runs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in HEALTHZ_PATHS:
            return JsonResponse({'status': 'ok'})
        return self.get_response(request)


class EnsureTenantContextMiddleware:
    """
    Ensure request.tenant exists even when host is not mapped directly
    (for example localhost development) and activate tenant's preferred language.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = get_request_tenant(request, required=False)
        language = self._resolve_language(tenant)
        if language:
            translation.activate(language)
            request.LANGUAGE_CODE = language
        try:
            return self.get_response(request)
        finally:
            translation.deactivate()

    @staticmethod
    def _resolve_language(tenant) -> str:
        if tenant is None:
            return ''
        language = str(getattr(tenant, 'language', '') or '').strip().lower()
        if language in SUPPORTED_LANGUAGES:
            return language
        return ''
