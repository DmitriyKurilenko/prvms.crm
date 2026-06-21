"""Deal → document data extraction and FieldMapping resolution.

Pure, request-agnostic helpers shared by `signing` and
`esign_agreement`. Kept separate so `esign_agreement` can reuse them
without importing `signing` (avoids an import cycle).
"""
from __future__ import annotations

from .models import DocumentTemplate


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
    # Табличная часть документа из позиций сделки (счёт/КП/акт). Lazy-импорт,
    # чтобы не создавать цикл documents↔crm на уровне модулей.
    from apps.crm.services.pricing import serialize_deal_items

    data.update(serialize_deal_items(deal))  # items[], subtotal, vat, total, has_items
    data.update(deal.custom_fields or {})
    return data


def _apply_field_mappings(data: dict, deal, template: DocumentTemplate):
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
