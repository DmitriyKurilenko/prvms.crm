"""Signing flow orchestration: document creation, OTP request, verify, email.

The OTP helpers (`_generate_otp`, `_send_otp`, ...) are imported into this
module's namespace; tests patch them at `apps.documents.signing.<name>`
because `request_signing_otp`/`verify_signing` execute here.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import SigningTokenLookup

from .esign_agreement import _ensure_esign_agreement
from .mapping import _apply_field_mappings, _extract_data_from_deal
from .models import Document, DocumentTemplate, SigningSession
from .otp import _generate_otp, _hash_otp, _send_otp, _verify_otp
from .pdf import _compute_pdf_hash, _regenerate_pdf_with_signature, _render_html, _render_pdf

logger = logging.getLogger(__name__)


class SigningError(Exception):
    pass


@dataclass
class SigningContext:
    tenant_id: int
    tenant_name: str
    document_id: int
    document_status: str
    token: str
    html_snapshot: str
    masked_phone: str = ''


def create_document_from_deal(deal, template: DocumentTemplate, created_by=None) -> Document:
    data = _extract_data_from_deal(deal)
    _apply_field_mappings(data, deal, template)
    html = _render_html(template.html_body, data)
    pdf = _render_pdf(html)
    filename = f'document_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    pdf_hash = _compute_pdf_hash(pdf)

    document = Document(
        template=template,
        template_version=template.version,
        document_type=template.document_type,
        crm_connection=None,
        crm_entity_type='deal',
        crm_entity_id=str(deal.id),
        deal=deal,
        filled_data=data,
        html_snapshot=html,
        status='draft',
        created_by=created_by,
        pdf_hash=pdf_hash,
    )
    document.pdf_file.save(filename, ContentFile(pdf), save=False)
    document.save()

    from apps.crm.models import Activity
    Activity.objects.create(
        activity_type='document',
        deal=deal,
        title=f'Создан документ: {template.name}',
        body=f'Шаблон «{template.name}», статус: черновик',
        status='done',
        created_by=created_by,
    )

    return document


def send_for_signing(document: Document, recipient: str) -> SigningSession:
    """Create a signing session. OTP is NOT sent yet — client requests it from the public page."""
    session = SigningSession.objects.create(
        document=document,
        otp_code_hash='',  # will be set when client requests OTP
        otp_sent_to=recipient,
        otp_expires_at=timezone.now() + timedelta(hours=24),  # session valid 24h
    )

    current_tenant = getattr(connection, 'tenant', None)
    with schema_context('public'):
        if current_tenant and getattr(current_tenant, 'schema_name', None) != 'public':
            SigningTokenLookup.objects.update_or_create(
                token=session.token,
                defaults={'tenant_id': current_tenant.id},
            )

    document.status = 'sent'
    document.save(update_fields=['status'])
    return session


def request_signing_otp(token: str) -> str | None:
    """Client requests OTP from public signing page. Returns test OTP in stub mode."""
    tenant, session = _resolve_signing_session(token)
    with tenant_context(tenant):
        session = SigningSession.objects.select_related('document').get(id=session.id)

        if session.verified_at:
            raise SigningError('Документ уже подписан')
        if session.attempts >= 5:
            raise SigningError('Превышено количество попыток')

        # Rate limit: max 3 OTP requests per session
        otp = _generate_otp()
        session.otp_code_hash = _hash_otp(otp)
        session.otp_expires_at = timezone.now() + timedelta(minutes=10)
        session.save(update_fields=['otp_code_hash', 'otp_expires_at'])

        document = session.document
        if document.status == 'sent':
            document.status = 'viewed'
            document.save(update_fields=['status'])

        _send_otp(session.otp_sent_to, otp, document.signing_method)

        provider = getattr(settings, 'SMS_PROVIDER', 'stub')
        api_key = getattr(settings, 'SMS_API_KEY', '')
        is_test = (provider == 'stub' or not api_key)
        return otp if is_test else None


def get_signing_context(token: str) -> SigningContext:
    tenant, session = _resolve_signing_session(token)
    return SigningContext(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        document_id=session.document_id,
        document_status=session.document.status,
        token=str(session.token),
        html_snapshot=session.document.html_snapshot,
        masked_phone=_mask_phone(session.otp_sent_to),
    )


def _mask_phone(phone: str) -> str:
    """Mask phone number: +7***4567"""
    if len(phone) <= 4:
        return '***'
    return phone[:2] + '***' + phone[-4:]


def verify_signing(token: str, code: str, ip_address: str | None, user_agent: str | None) -> Document:
    tenant, session = _resolve_signing_session(token)
    with tenant_context(tenant):
        session = SigningSession.objects.select_related('document').get(id=session.id)

        if session.verified_at:
            return session.document
        if session.attempts >= 5:
            raise SigningError('Too many attempts')
        if timezone.now() > session.otp_expires_at:
            session.document.status = 'expired'
            session.document.save(update_fields=['status'])
            raise SigningError('OTP expired')

        if not _verify_otp(code, session.otp_code_hash):
            session.attempts += 1
            session.save(update_fields=['attempts'])
            raise SigningError('Invalid OTP')

        session.verified_at = timezone.now()
        session.ip_address = ip_address
        session.user_agent = (user_agent or '')[:1000]
        session.attempts += 1
        session.save(update_fields=['verified_at', 'ip_address', 'user_agent', 'attempts'])

        document = session.document
        document.status = 'signed'
        document.signed_at = timezone.now()
        document.signer_ip = ip_address
        document.signer_user_agent = (user_agent or '')[:1000]

        # Create electronic signature (ПЭП / simple electronic signature)
        document.signature_data = _build_signature_record(document, session, ip_address, user_agent)

        document.save(update_fields=[
            'status', 'signed_at', 'signer_ip', 'signer_user_agent', 'signature_data',
        ])

        # Regenerate PDF with electronic signature block appended
        _regenerate_pdf_with_signature(document)

        # Auto-sign e-agreement if this is the contact's first signed document
        _ensure_esign_agreement(document, session, ip_address, user_agent)

    with schema_context('public'):
        SigningTokenLookup.objects.filter(token=session.token).update(used_at=timezone.now())
        from .tasks import notify_document_signed

        notify_document_signed.delay(tenant.id, document.id)

    return document


def _resolve_signing_session(token: str):
    with schema_context('public'):
        lookup = SigningTokenLookup.objects.select_related('tenant').filter(token=token).first()
    if not lookup:
        raise SigningError('Signing token not found')

    with tenant_context(lookup.tenant):
        session = SigningSession.objects.select_related('document').filter(token=token).first()
        if not session:
            raise SigningError('Signing session not found')
        if session.document.status == 'draft':
            session.document.status = 'viewed'
            session.document.save(update_fields=['status'])
    return lookup.tenant, session


def send_signed_document_email(token: str, email: str):
    """Send the signed document PDF to the specified email address."""
    tenant, session = _resolve_signing_session(token)
    with tenant_context(tenant):
        session = SigningSession.objects.select_related('document').get(id=session.id)
        document = session.document
        if document.status != 'signed':
            raise SigningError('Документ ещё не подписан')
        if not document.pdf_file:
            raise SigningError('PDF файл не найден')

        document.pdf_file.open('rb')
        pdf_data = document.pdf_file.read()
        document.pdf_file.close()

        from django.core.mail import EmailMessage
        msg = EmailMessage(
            subject=f'Подписанный документ #{document.id}',
            body=f'Во вложении подписанный документ #{document.id}.\n\nДата подписания: {document.signed_at.strftime("%d.%m.%Y %H:%M") if document.signed_at else "—"}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach(f'document_{document.id}_signed.pdf', pdf_data, 'application/pdf')
        msg.send(fail_silently=False)


def _build_signature_record(
    document: Document,
    session: SigningSession,
    ip_address: str | None,
    user_agent: str | None,
) -> dict:
    """Build a simple electronic signature (ПЭП) record per 63-ФЗ."""
    now = timezone.now()
    # Recompute PDF hash to verify document integrity
    pdf_hash = document.pdf_hash
    if document.pdf_file:
        try:
            document.pdf_file.open('rb')
            pdf_hash = _compute_pdf_hash(document.pdf_file.read())
            document.pdf_file.close()
        except (FileNotFoundError, OSError):
            # Fall back to stored hash; the PDF storage may be unavailable transiently.
            logger.warning('Could not reopen PDF for document %s; using stored hash', document.id)

    # Create HMAC signature over the signing data
    sign_payload = f'{document.id}:{pdf_hash}:{session.otp_sent_to}:{now.isoformat()}:{ip_address}'
    signature_hmac = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        sign_payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    return {
        'version': 1,
        'type': 'simple_electronic_signature',
        'algorithm': 'HMAC-SHA256',
        'document_id': document.id,
        'pdf_hash_sha256': pdf_hash,
        'pdf_hash_verified': pdf_hash == document.pdf_hash,
        'signer_phone': session.otp_sent_to,
        'signer_ip': ip_address,
        'signer_user_agent': (user_agent or '')[:500],
        'signed_at': now.isoformat(),
        'otp_session_id': str(session.token),
        'signature': signature_hmac,
    }
