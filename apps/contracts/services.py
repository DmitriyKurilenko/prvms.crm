from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import connection
from django.template import Context, Template
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context
from weasyprint import HTML

from apps.tenants.models import SigningTokenLookup
from .models import Contract, ContractTemplate, SigningSession

logger = logging.getLogger(__name__)


class SigningError(Exception):
    pass


@dataclass
class SigningContext:
    tenant_id: int
    tenant_name: str
    contract_id: int
    contract_status: str
    token: str
    html_snapshot: str
    masked_phone: str = ''


def create_contract_from_deal(deal, template: ContractTemplate, created_by=None) -> Contract:
    data = _extract_data_from_deal(deal)
    _apply_field_mappings(data, deal, template)
    html = _render_html(template.html_body, data)
    pdf = _render_pdf(html)
    filename = f'contract_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    pdf_hash = _compute_pdf_hash(pdf)

    contract = Contract(
        template=template,
        template_version=template.version,
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
    contract.pdf_file.save(filename, ContentFile(pdf), save=False)
    contract.save()

    from apps.crm.models import Activity
    Activity.objects.create(
        activity_type='contract',
        deal=deal,
        title=f'Создан договор: {template.name}',
        body=f'Шаблон «{template.name}», статус: черновик',
        status='done',
        created_by=created_by,
    )

    return contract


def send_for_signing(contract: Contract, recipient: str) -> SigningSession:
    """Create a signing session. OTP is NOT sent yet — client requests it from the public page."""
    session = SigningSession.objects.create(
        contract=contract,
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

    contract.status = 'sent'
    contract.save(update_fields=['status'])
    return session


def request_signing_otp(token: str) -> str | None:
    """Client requests OTP from public signing page. Returns test OTP in stub mode."""
    tenant, session = _resolve_signing_session(token)
    with tenant_context(tenant):
        session = SigningSession.objects.select_related('contract').get(id=session.id)

        if session.verified_at:
            raise SigningError('Договор уже подписан')
        if session.attempts >= 5:
            raise SigningError('Превышено количество попыток')

        # Rate limit: max 3 OTP requests per session
        otp = _generate_otp()
        session.otp_code_hash = _hash_otp(otp)
        session.otp_expires_at = timezone.now() + timedelta(minutes=10)
        session.save(update_fields=['otp_code_hash', 'otp_expires_at'])

        contract = session.contract
        if contract.status == 'sent':
            contract.status = 'viewed'
            contract.save(update_fields=['status'])

        _send_otp(session.otp_sent_to, otp, contract.signing_method)

        provider = getattr(settings, 'SMS_PROVIDER', 'stub')
        api_key = getattr(settings, 'SMS_API_KEY', '')
        is_test = (provider == 'stub' or not api_key)
        return otp if is_test else None


def get_signing_context(token: str) -> SigningContext:
    tenant, session = _resolve_signing_session(token)
    return SigningContext(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        contract_id=session.contract_id,
        contract_status=session.contract.status,
        token=str(session.token),
        html_snapshot=session.contract.html_snapshot,
        masked_phone=_mask_phone(session.otp_sent_to),
    )


def _mask_phone(phone: str) -> str:
    """Mask phone number: +7***4567"""
    if len(phone) <= 4:
        return '***'
    return phone[:2] + '***' + phone[-4:]


def verify_signing(token: str, code: str, ip_address: str | None, user_agent: str | None) -> Contract:
    tenant, session = _resolve_signing_session(token)
    with tenant_context(tenant):
        session = SigningSession.objects.select_related('contract').get(id=session.id)

        if session.verified_at:
            return session.contract
        if session.attempts >= 5:
            raise SigningError('Too many attempts')
        if timezone.now() > session.otp_expires_at:
            session.contract.status = 'expired'
            session.contract.save(update_fields=['status'])
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

        contract = session.contract
        contract.status = 'signed'
        contract.signed_at = timezone.now()
        contract.signer_ip = ip_address
        contract.signer_user_agent = (user_agent or '')[:1000]

        # Create electronic signature (ПЭП / simple electronic signature)
        contract.signature_data = _build_signature_record(contract, session, ip_address, user_agent)

        contract.save(update_fields=[
            'status', 'signed_at', 'signer_ip', 'signer_user_agent', 'signature_data',
        ])

        # Regenerate PDF with electronic signature block appended
        _regenerate_pdf_with_signature(contract)

        # Auto-sign e-agreement if this is the contact's first signed contract
        _ensure_esign_agreement(contract, session, ip_address, user_agent)

    with schema_context('public'):
        SigningTokenLookup.objects.filter(token=session.token).update(used_at=timezone.now())
        from .tasks import notify_contract_signed

        notify_contract_signed.delay(tenant.id, contract.id)

    return contract


def _resolve_signing_session(token: str):
    with schema_context('public'):
        lookup = SigningTokenLookup.objects.select_related('tenant').filter(token=token).first()
    if not lookup:
        raise SigningError('Signing token not found')

    with tenant_context(lookup.tenant):
        session = SigningSession.objects.select_related('contract').filter(token=token).first()
        if not session:
            raise SigningError('Signing session not found')
        if session.contract.status == 'draft':
            session.contract.status = 'viewed'
            session.contract.save(update_fields=['status'])
    return lookup.tenant, session


def _extract_data_from_deal(deal) -> dict:
    data = {
        'deal_id': deal.id,
        'deal_name': deal.name,
        'amount': str(deal.amount) if deal.amount is not None else '',
        'currency': deal.currency,
        'contact_name': str(deal.contact) if deal.contact else '',
        'company_name': deal.company.name if deal.company else '',
        'created_at': deal.created_at.isoformat(),
    }
    data.update(deal.custom_fields or {})
    return data


def _apply_field_mappings(data: dict, deal, template: ContractTemplate):
    """Apply FieldMapping rules: resolve crm_field_path on the deal and set variable_key in data."""
    from .models import FieldMapping

    mappings = FieldMapping.objects.filter(template=template)
    for mapping in mappings:
        value = _resolve_field_path(deal, mapping.crm_field_path)
        if value is not None:
            data[mapping.variable_key] = value


def _resolve_field_path(obj, path: str):
    """Resolve a dotted path like 'contact.phone' on a Django model instance."""
    parts = path.split('.')
    current = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return str(current) if current is not None else None


def _render_html(raw_template: str, data: dict) -> str:
    template = Template(raw_template)
    return template.render(Context(data))


def _render_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def _regenerate_pdf_with_signature(contract: Contract):
    """Re-render the contract PDF with an electronic signature block appended."""
    sig = contract.signature_data or {}
    signed_at = sig.get('signed_at', '')
    signer_phone = sig.get('signer_phone', '')
    signature_hash = sig.get('signature', '')
    pdf_hash = sig.get('pdf_hash_sha256', '')
    signer_ip = sig.get('signer_ip', '—')
    session_id = sig.get('otp_session_id', '—')

    signature_html = f'''
    <div style="margin-top: 40px; padding: 20px; border: 2px solid #166534; border-radius: 8px; background: #f0fdf4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; page-break-inside: avoid;">
        <div style="display: flex; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #bbf7d0; padding-bottom: 10px;">
            <span style="font-size: 24px; margin-right: 8px;">✅</span>
            <span style="font-size: 16px; font-weight: 700; color: #166534;">Документ подписан простой электронной подписью (ПЭП)</span>
        </div>
        <table style="width: 100%; font-size: 13px; color: #333; border-collapse: collapse;">
            <tr><td style="padding: 4px 8px; font-weight: 600; width: 200px;">Дата подписания</td><td style="padding: 4px 8px;">{signed_at[:19].replace("T", " ")}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">Телефон подписанта</td><td style="padding: 4px 8px;">{signer_phone}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">IP-адрес подписанта</td><td style="padding: 4px 8px;">{signer_ip}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">Идентификатор сессии</td><td style="padding: 4px 8px; font-family: monospace; font-size: 11px; word-break: break-all;">{session_id}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">Хеш документа (SHA-256)</td><td style="padding: 4px 8px; font-family: monospace; font-size: 11px; word-break: break-all;">{pdf_hash}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">Подпись (HMAC-SHA256)</td><td style="padding: 4px 8px; font-family: monospace; font-size: 11px; word-break: break-all;">{signature_hash}</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">Метод подтверждения</td><td style="padding: 4px 8px;">SMS OTP</td></tr>
            <tr><td style="padding: 4px 8px; font-weight: 600;">Тип подписи</td><td style="padding: 4px 8px;">Простая электронная подпись (ПЭП)</td></tr>
        </table>
        <p style="font-size: 11px; color: #888; margin: 10px 0 0; border-top: 1px solid #bbf7d0; padding-top: 8px;">
            Подписано в соответствии с Федеральным законом от 06.04.2011 №63-ФЗ «Об электронной подписи» (ст. 6, ст. 9).
            Документ имеет юридическую силу при наличии соглашения об использовании электронной подписи между сторонами. Договор #{ contract.id }.
        </p>
    </div>
    '''

    full_html = contract.html_snapshot + signature_html
    try:
        pdf_bytes = HTML(string=full_html).write_pdf()
        contract.html_snapshot = full_html
        contract.pdf_file.save(
            f'contract_{contract.id}_signed.pdf',
            ContentFile(pdf_bytes),
            save=False,
        )
        contract.save(update_fields=['pdf_file', 'html_snapshot'])
    except Exception:
        logger.exception('Failed to regenerate PDF with signature block for contract %s', contract.id)


def _ensure_esign_agreement(contract: Contract, session: SigningSession, ip_address, user_agent):
    """Auto-create and sign e-signing agreement if this contact hasn't signed one yet."""
    deal = contract.deal
    if not deal or not deal.contact_id:
        return

    from apps.crm.models import Contact
    contact = Contact.objects.filter(id=deal.contact_id).first()
    if not contact or contact.esign_agreement_signed_at:
        return  # already signed

    template = ContractTemplate.objects.filter(
        name='Соглашение об использовании электронной подписи',
        is_system=True,
        is_active=True,
    ).first()
    if not template:
        logger.warning('E-sign agreement template not found, skipping auto-sign')
        return

    try:
        # Generate the agreement contract
        data = _extract_data_from_deal(deal)
        _apply_field_mappings(data, deal, template)
        html = _render_html(template.html_body, data)
        pdf = _render_pdf(html)
        pdf_hash = _compute_pdf_hash(pdf)

        agreement = Contract(
            template=template,
            template_version=template.version,
            crm_connection=None,
            crm_entity_type='deal',
            crm_entity_id=str(deal.id),
            deal=deal,
            filled_data=data,
            html_snapshot=html,
            status='signed',
            created_by=contract.created_by,
            pdf_hash=pdf_hash,
            signed_at=timezone.now(),
            signer_ip=ip_address,
            signer_user_agent=(user_agent or '')[:1000],
        )
        agreement.pdf_file.save(
            f'esign_agreement_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            ContentFile(pdf),
            save=False,
        )

        # Build signature record for the agreement (same signer data)
        agreement.signature_data = {
            'type': 'simple_electronic_signature',
            'version': 1,
            'algorithm': 'HMAC-SHA256',
            'signed_at': timezone.now().isoformat(),
            'signer_phone': session.otp_sent_to,
            'signer_ip': ip_address,
            'otp_session_id': str(session.token),
            'pdf_hash_sha256': pdf_hash,
            'contract_id': 0,  # will be set after save
            'note': f'Подписано автоматически при подписании договора #{contract.id}',
        }
        agreement.save()
        agreement.signature_data['contract_id'] = agreement.id

        # Compute HMAC signature
        sig_payload = f'{agreement.id}:{pdf_hash}:{session.otp_sent_to}:{agreement.signed_at.isoformat()}'
        agreement.signature_data['signature'] = hmac.new(
            settings.SECRET_KEY.encode(),
            sig_payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        agreement.save(update_fields=['signature_data'])

        # Regenerate PDF with signature block
        _regenerate_pdf_with_signature(agreement)

        # Update contact
        contact.esign_agreement_signed_at = agreement.signed_at
        contact.esign_agreement_id = agreement.id
        contact.save(update_fields=['esign_agreement_signed_at', 'esign_agreement_id'])

        from apps.crm.models import Activity
        Activity.objects.create(
            activity_type='contract',
            deal=deal,
            contact=contact,
            title='Подписано соглашение об использовании ЭП',
            body=f'Соглашение #{agreement.id} подписано автоматически при подписании договора #{contract.id}',
            status='done',
            created_by=contract.created_by,
        )

        logger.info('Auto-signed e-sign agreement #%s for contact #%s', agreement.id, contact.id)
    except Exception:
        logger.exception('Failed to auto-sign e-agreement for contact #%s', contact.id)


def send_signed_contract_email(token: str, email: str):
    """Send the signed contract PDF to the specified email address."""
    tenant, session = _resolve_signing_session(token)
    with tenant_context(tenant):
        session = SigningSession.objects.select_related('contract').get(id=session.id)
        contract = session.contract
        if contract.status != 'signed':
            raise SigningError('Договор ещё не подписан')
        if not contract.pdf_file:
            raise SigningError('PDF файл не найден')

        contract.pdf_file.open('rb')
        pdf_data = contract.pdf_file.read()
        contract.pdf_file.close()

        from django.core.mail import EmailMessage
        msg = EmailMessage(
            subject=f'Подписанный договор #{contract.id}',
            body=f'Во вложении подписанный договор #{contract.id}.\n\nДата подписания: {contract.signed_at.strftime("%d.%m.%Y %H:%M") if contract.signed_at else "—"}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach(f'contract_{contract.id}_signed.pdf', pdf_data, 'application/pdf')
        msg.send(fail_silently=False)


def _compute_pdf_hash(pdf_bytes: bytes) -> str:
    """Compute SHA-256 hash of PDF document."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def _build_signature_record(
    contract: Contract,
    session: SigningSession,
    ip_address: str | None,
    user_agent: str | None,
) -> dict:
    """Build a simple electronic signature (ПЭП) record per 63-ФЗ."""
    now = timezone.now()
    # Recompute PDF hash to verify document integrity
    pdf_hash = contract.pdf_hash
    if contract.pdf_file:
        try:
            contract.pdf_file.open('rb')
            pdf_hash = _compute_pdf_hash(contract.pdf_file.read())
            contract.pdf_file.close()
        except Exception:
            pass

    # Create HMAC signature over the signing data
    sign_payload = f'{contract.id}:{pdf_hash}:{session.otp_sent_to}:{now.isoformat()}:{ip_address}'
    signature_hmac = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        sign_payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    return {
        'version': 1,
        'type': 'simple_electronic_signature',
        'algorithm': 'HMAC-SHA256',
        'contract_id': contract.id,
        'pdf_hash_sha256': pdf_hash,
        'pdf_hash_verified': pdf_hash == contract.pdf_hash,
        'signer_phone': session.otp_sent_to,
        'signer_ip': ip_address,
        'signer_user_agent': (user_agent or '')[:500],
        'signed_at': now.isoformat(),
        'otp_session_id': str(session.token),
        'signature': signature_hmac,
    }


def _generate_otp() -> str:
    return ''.join(str(secrets.randbelow(10)) for _ in range(6))


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def _verify_otp(code: str, otp_hash: str) -> bool:
    return hmac.compare_digest(_hash_otp(code), otp_hash)


def _send_otp(recipient: str, code: str, method: str):
    if method == 'email_otp':
        send_mail(
            subject='Код подтверждения договора',
            message=f'Ваш код подтверждения: {code}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
        return
    # SMS OTP
    _send_sms(recipient, f'Код подтверждения договора: {code}')


def _send_sms(phone: str, message: str):
    """Send SMS via configured provider."""
    import requests as _requests

    provider = getattr(settings, 'SMS_PROVIDER', 'stub')
    api_key = getattr(settings, 'SMS_API_KEY', '')
    sender_name = getattr(settings, 'SMS_SENDER_NAME', 'Platform')

    if provider == 'stub' or not api_key:
        logger.info('SMS stub: phone=%s message=%s', phone, message)
        return

    if provider == 'smsru':
        resp = _requests.get(
            'https://sms.ru/sms/send',
            params={
                'api_id': api_key,
                'to': phone,
                'msg': message,
                'json': 1,
                'from': sender_name,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'OK':
            logger.error('sms.ru send failed: %s', data)
    elif provider == 'smsc':
        resp = _requests.post(
            'https://smsc.ru/sys/send.php',
            data={
                'login': getattr(settings, 'SMS_SMSC_LOGIN', ''),
                'psw': api_key,
                'phones': phone,
                'mes': message,
                'sender': sender_name,
                'fmt': 3,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            logger.error('SMSC send failed: %s', data)
    else:
        logger.warning('Unknown SMS provider: %s, message not sent', provider)
