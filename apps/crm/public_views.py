"""Публичные обработчики веб-форм захвата лидов.

Резолв тенанта по публичному токену через shared-lookup `WebFormLookup`,
далее работа в схеме тенанта. Паттерн honeypot + rate-limit повторяет
`apps/billing/public_views.py`. CORS открывается под `allowed_origins` формы,
чтобы виджет работал с сайта клиента.
"""
from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_tenants.utils import schema_context

logger = logging.getLogger('crm.webform')


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', 'unknown')


def _resolve_tenant(token):
    with schema_context('public'):
        from apps.tenants.models import WebFormLookup
        return (
            WebFormLookup.objects.filter(token=token, is_active=True)
            .select_related('tenant')
            .first()
        )


def _apply_cors(response, request, allowed_origins: list):
    origin = request.META.get('HTTP_ORIGIN')
    if not allowed_origins:
        response['Access-Control-Allow-Origin'] = origin or '*'
    elif origin in allowed_origins:
        response['Access-Control-Allow-Origin'] = origin
    response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Vary'] = 'Origin'
    return response


@csrf_exempt
def webform_schema(request, token):
    """Публичное описание формы для рендера виджетом."""
    lookup = _resolve_tenant(token)
    if not lookup:
        return JsonResponse({'detail': 'Form not found'}, status=404)
    with schema_context(lookup.tenant.schema_name):
        from apps.crm.models import WebForm
        form = WebForm.objects.filter(public_token=token, is_active=True).first()
        if not form:
            return JsonResponse({'detail': 'Form not found'}, status=404)
        from apps.crm.services.captcha import captcha_site_info
        payload = {
            'name': form.name,
            'fields': form.fields_schema,
            'success_message': form.success_message,
            'captcha': captcha_site_info(),
        }
        allowed = form.allowed_origins
    return _apply_cors(JsonResponse(payload), request, allowed)


@csrf_exempt
def webform_submit(request, token):
    if request.method == 'OPTIONS':
        return _apply_cors(JsonResponse({}), request, [])
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    if data.get('website'):  # honeypot
        return JsonResponse({'detail': 'Bad request'}, status=400)

    client_ip = _get_client_ip(request)

    from apps.crm.services.captcha import captcha_enabled, verify_captcha
    if captcha_enabled() and not verify_captcha(str(data.get('captcha') or ''), client_ip):
        return JsonResponse({'detail': 'Проверка капчи не пройдена'}, status=400)

    cache_key = f'webform:{token}:{client_ip}'
    if cache.get(cache_key):
        return JsonResponse({'detail': 'Слишком много запросов. Попробуйте позже.'}, status=429)
    cache.set(cache_key, True, timeout=30)

    lookup = _resolve_tenant(token)
    if not lookup:
        return JsonResponse({'detail': 'Form not found'}, status=404)

    fields = data.get('fields') if isinstance(data.get('fields'), dict) else {}
    with schema_context(lookup.tenant.schema_name):
        from apps.crm.models import WebForm
        from apps.crm.services.webform_intake import intake_webform_submission
        result = intake_webform_submission(lookup.tenant, token, fields)
        allowed = []
        f = WebForm.objects.filter(public_token=token).first()
        if f:
            allowed = f.allowed_origins
    if not result:
        return JsonResponse({'detail': 'Form inactive'}, status=404)
    return _apply_cors(JsonResponse({'status': 'ok', 'message': result['success_message']}), request, allowed)
