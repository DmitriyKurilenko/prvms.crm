from __future__ import annotations

import ipaddress
import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import (
    XML_NOT_FOUND,
    build_configuration_xml,
    build_dialplan_decision,
    build_dialplan_xml,
    build_directory_xml,
    resolve_tenant_for_telephony,
)
from .tasks import process_freeswitch_cdr

_XML_CT = 'text/xml; charset=utf-8'


def _request_payload(request) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST.dict() if request.POST else {}


def _ip_allowed(remote_addr: str, allowed_values: list[str]) -> bool:
    if not remote_addr:
        return False
    for item in allowed_values:
        item = str(item).strip()
        if not item:
            continue
        if item == remote_addr:
            return True
        try:
            network = ipaddress.ip_network(item, strict=False)
            if ipaddress.ip_address(remote_addr) in network:
                return True
        except ValueError:
            pass
    return False


def _ip_authorized(request) -> bool:
    return _ip_allowed(request.META.get('REMOTE_ADDR', ''), settings.FREESWITCH_ALLOWED_IPS)


def _token_authorized(request) -> bool:
    return request.headers.get('X-FreeSWITCH-Token') == settings.FREESWITCH_ESL_PASSWORD


# mod_xml_curl (dialplan + directory): IP-only — FS does not send a token header
# events (CDR Lua hook): token + IP — the Lua script includes the token
@csrf_exempt
@require_POST
def dialplan(request):
    if not _ip_authorized(request):
        return HttpResponse(XML_NOT_FOUND, content_type=_XML_CT, status=403)
    payload = _request_payload(request)
    tenant = resolve_tenant_for_telephony(payload)
    if not tenant:
        return HttpResponse(XML_NOT_FOUND, content_type=_XML_CT, status=404)
    decision = build_dialplan_decision(tenant, payload)
    return HttpResponse(build_dialplan_xml(tenant.slug, decision), content_type=_XML_CT)


@csrf_exempt
@require_POST
def directory(request):
    if not _ip_authorized(request):
        return HttpResponse(XML_NOT_FOUND, content_type=_XML_CT, status=403)
    payload = _request_payload(request)
    extension_num = payload.get('user') or payload.get('extension') or ''
    domain = payload.get('domain') or payload.get('key_value') or 'freeswitch.local'
    tenant = resolve_tenant_for_telephony(payload)
    return HttpResponse(build_directory_xml(tenant, extension_num, domain), content_type=_XML_CT)


@csrf_exempt
@require_POST
def configuration(request):
    if not _ip_authorized(request):
        return HttpResponse(XML_NOT_FOUND, content_type=_XML_CT, status=403)
    return HttpResponse(build_configuration_xml(), content_type=_XML_CT)


@csrf_exempt
@require_POST
def events(request):
    if not (_token_authorized(request) and _ip_authorized(request)):
        return JsonResponse({'detail': 'Forbidden'}, status=403)
    payload = _request_payload(request)
    tenant = resolve_tenant_for_telephony(payload)
    if not tenant:
        return JsonResponse({'detail': 'Tenant not found for telephony request'}, status=404)
    process_freeswitch_cdr.delay(tenant.id, payload)
    return JsonResponse({'detail': 'accepted', 'tenant_slug': tenant.slug})
