"""Backwards-compatible aggregator for `apps.contracts.services`.

The implementation was split by responsibility:
- `mapping`   — deal → contract data extraction / FieldMapping
- `pdf`       — HTML/PDF rendering, signed-PDF regeneration
- `otp`       — OTP generate/hash/verify/send (SMS/email)
- `esign_agreement` — auto-sign of the ЭП usage agreement
- `signing`   — flow orchestration (create/send/request-otp/verify/email)

This shim re-exports the public API plus the internal helpers that
`apps.contracts.{api,public_views,tasks}` import as
`from .services import ...`, so all existing imports keep working.

NOTE: `test_signing_flow` patches `_send_otp`/`_generate_otp` at
`apps.contracts.signing.*` (where `request_signing_otp` executes), not
here — patching this shim would not affect the call sites.
"""
from .mapping import _apply_field_mappings, _extract_data_from_deal, _resolve_field_path
from .pdf import (
    _compute_pdf_hash,
    _regenerate_pdf_with_signature,
    _render_html,
    _render_pdf,
)
from .otp import _generate_otp, _hash_otp, _send_otp, _send_sms, _verify_otp
from .esign_agreement import _ensure_esign_agreement
from .signing import (
    SigningContext,
    SigningError,
    _build_signature_record,
    _mask_phone,
    _resolve_signing_session,
    create_contract_from_deal,
    get_signing_context,
    request_signing_otp,
    send_for_signing,
    send_signed_contract_email,
    verify_signing,
)

__all__ = [
    'SigningContext',
    'SigningError',
    'create_contract_from_deal',
    'send_for_signing',
    'request_signing_otp',
    'get_signing_context',
    'verify_signing',
    'send_signed_contract_email',
    '_resolve_signing_session',
    '_mask_phone',
    '_build_signature_record',
    '_extract_data_from_deal',
    '_apply_field_mappings',
    '_resolve_field_path',
    '_render_html',
    '_render_pdf',
    '_compute_pdf_hash',
    '_regenerate_pdf_with_signature',
    '_ensure_esign_agreement',
    '_generate_otp',
    '_hash_otp',
    '_verify_otp',
    '_send_otp',
    '_send_sms',
]
