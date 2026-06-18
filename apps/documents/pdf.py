"""Document HTML/PDF rendering and signed-PDF regeneration."""
from __future__ import annotations

import hashlib
import logging

from django.core.files.base import ContentFile
from django.template import Context, Template
from weasyprint import HTML

from .models import Document

logger = logging.getLogger(__name__)


def _render_html(raw_template: str, data: dict) -> str:
    template = Template(raw_template)
    return template.render(Context(data))


def _render_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def _compute_pdf_hash(pdf_bytes: bytes) -> str:
    """Compute SHA-256 hash of PDF document."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def _regenerate_pdf_with_signature(document: Document):
    """Re-render the document PDF with an electronic signature block appended."""
    sig = document.signature_data or {}
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
            Документ имеет юридическую силу при наличии соглашения об использовании электронной подписи между сторонами. Документ #{ document.id }.
        </p>
    </div>
    '''

    full_html = document.html_snapshot + signature_html
    try:
        pdf_bytes = HTML(string=full_html).write_pdf()
        document.html_snapshot = full_html
        document.pdf_file.save(
            f'document_{document.id}_signed.pdf',
            ContentFile(pdf_bytes),
            save=False,
        )
        document.save(update_fields=['pdf_file', 'html_snapshot'])
    except Exception:
        logger.exception('Failed to regenerate PDF with signature block for document %s', document.id)
