from __future__ import annotations

import logging

from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .services import (
    SigningError,
    _resolve_signing_session,
    get_signing_context,
    request_signing_otp,
    send_signed_document_email,
    verify_signing,
)

logger = logging.getLogger(__name__)


@require_GET
def sign_esign_agreement(request, token: str):
    """Public view: render the e-signing agreement text for review before signing."""
    from django_tenants.utils import tenant_context

    from .models import DocumentTemplate
    from .services import _apply_field_mappings, _extract_data_from_deal, _render_html
    try:
        tenant, session = _resolve_signing_session(str(token))
    except SigningError as exc:
        return render(request, 'signing.html', {'error': str(exc)}, status=404)
    with tenant_context(tenant):
        from .models import SigningSession
        session = SigningSession.objects.select_related('document__deal').get(id=session.id)
        template = DocumentTemplate.objects.filter(
            name='Соглашение об использовании электронной подписи',
            is_system=True,
            is_active=True,
        ).first()
        if not template:
            return render(request, 'signing.html', {'error': 'Шаблон соглашения не найден'}, status=404)
        deal = session.document.deal
        if deal:
            data = _extract_data_from_deal(deal)
            _apply_field_mappings(data, deal, template)
        else:
            data = {}
        html_body = _render_html(template.html_body, data)
    return render(request, 'esign_agreement.html', {
        'tenant_name': tenant.name,
        'html_body': html_body,
    })


@require_GET
def sign_page(request, token: str):
    try:
        context = get_signing_context(token)
    except SigningError as exc:
        return render(request, 'signing.html', {'error': str(exc)}, status=404)
    return render(
        request,
        'signing.html',
        {
            'tenant_name': context.tenant_name,
            'document_id': context.document_id,
            'document_status': context.document_status,
            'token': context.token,
            'html_snapshot': context.html_snapshot,
            'masked_phone': context.masked_phone,
        },
    )


@csrf_exempt
@require_POST
def sign_request_otp(request, token: str):
    """Client requests OTP from public signing page."""
    try:
        test_otp = request_signing_otp(str(token))
    except SigningError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    result = {'detail': 'sent'}
    if test_otp:
        result['test_otp'] = test_otp
    return JsonResponse(result)


@csrf_exempt
@require_POST
def sign_verify(request, token: str):
    code = request.POST.get('code') or ''
    esign_consent = request.POST.get('esign_consent') == '1'
    if not code or not esign_consent:
        # Re-render the signing page with error
        try:
            context = get_signing_context(token)
        except SigningError:
            return render(request, 'signing.html', {'error': 'Сессия подписания не найдена'}, status=404)
        form_error = 'Введите код подтверждения' if not code else 'Необходимо принять условия электронной подписи'
        return render(request, 'signing.html', {
            'tenant_name': context.tenant_name,
            'document_id': context.document_id,
            'document_status': context.document_status,
            'token': context.token,
            'html_snapshot': context.html_snapshot,
            'masked_phone': context.masked_phone,
            'form_error': form_error,
        })
    try:
        document = verify_signing(token, code, request.META.get('REMOTE_ADDR'), request.META.get('HTTP_USER_AGENT'))
    except SigningError as exc:
        try:
            context = get_signing_context(token)
        except SigningError:
            return render(request, 'signing.html', {'error': str(exc)}, status=400)
        return render(request, 'signing.html', {
            'tenant_name': context.tenant_name,
            'document_id': context.document_id,
            'document_status': context.document_status,
            'token': context.token,
            'html_snapshot': context.html_snapshot,
            'masked_phone': context.masked_phone,
            'form_error': str(exc),
        })
    return render(request, 'signing_success.html', {
        'document_id': document.id,
        'signed_at': document.signed_at,
        'token': token,
    })


@require_GET
def sign_download_pdf(request, token: str):
    """Download signed document PDF (public, no auth)."""
    from django_tenants.utils import tenant_context
    try:
        tenant, session = _resolve_signing_session(str(token))
    except SigningError as exc:
        return JsonResponse({'error': str(exc)}, status=404)
    with tenant_context(tenant):
        document = session.document
        if document.status != 'signed':
            return JsonResponse({'error': 'Документ ещё не подписан'}, status=400)
        if not document.pdf_file:
            return JsonResponse({'error': 'PDF не найден'}, status=404)
        return FileResponse(
            document.pdf_file.open('rb'),
            filename=f'document_{document.id}_signed.pdf',
            content_type='application/pdf',
        )


@csrf_exempt
@require_POST
def sign_send_email(request, token: str):
    """Send signed document PDF to email (public, from success page)."""
    import json
    try:
        body = json.loads(request.body)
        email = body.get('email', '').strip()
    except (json.JSONDecodeError, AttributeError):
        email = request.POST.get('email', '').strip()
    if not email or '@' not in email:
        return JsonResponse({'error': 'Укажите корректный email'}, status=400)
    try:
        send_signed_document_email(str(token), email)
    except SigningError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        # Email delivery / PDF rendering / SMTP / S3 — depends on env. Log details, return generic 500 to client.
        logger.exception('Failed to send signed document email for token %s', token)
        return JsonResponse({'error': 'Ошибка отправки email'}, status=500)
    return JsonResponse({'detail': 'sent'})
