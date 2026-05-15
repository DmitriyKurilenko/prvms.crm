"""Auto-creation and auto-signing of the e-signature usage agreement.

Imports only from `mapping` and `pdf` (never from `signing`) so the
`signing` → `esign_agreement` dependency stays acyclic.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .mapping import _apply_field_mappings, _extract_data_from_deal
from .models import Contract, ContractTemplate, SigningSession
from .pdf import _compute_pdf_hash, _regenerate_pdf_with_signature, _render_html, _render_pdf

logger = logging.getLogger(__name__)


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
