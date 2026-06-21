"""Пересчёт суммы сделки из её позиций. Единая политика округления.

Источник истины для `Deal.amount`, когда у сделки есть позиции: сумма
`line_total` всех `DealItem`. При отсутствии позиций сумма не трогается —
остаётся введённой вручную.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from apps.crm.models import Deal

_CENTS = Decimal('0.01')


def _round(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def recalc_deal_amount(deal: Deal) -> Decimal:
    """Пересчитать и сохранить `Deal.amount` по позициям.

    Если позиций нет — возвращает текущую сумму без изменений.
    """
    items = list(deal.items.all())
    if not items:
        return deal.amount if deal.amount is not None else Decimal('0')
    total = _round(sum((item.line_total for item in items), Decimal('0')))
    Deal.objects.filter(id=deal.id).update(amount=total)
    deal.amount = total
    return total


def serialize_deal_items(deal: Deal) -> dict:
    """Сериализация позиций сделки с итогами для API и шаблонов документов."""
    items = list(deal.items.select_related('product').all())
    subtotal = _round(sum((i.line_subtotal for i in items), Decimal('0')))
    vat = _round(sum((i.line_vat for i in items), Decimal('0')))
    total = _round(sum((i.line_total for i in items), Decimal('0')))
    return {
        'items': [
            {
                'id': i.id,
                'product_id': i.product_id,
                'name': i.name_snapshot,
                'quantity': float(i.quantity),
                'price': float(i.price),
                'discount_percent': float(i.discount_percent),
                'vat_rate': float(i.vat_rate),
                'line_subtotal': float(_round(i.line_subtotal)),
                'line_vat': float(_round(i.line_vat)),
                'line_total': float(_round(i.line_total)),
            }
            for i in items
        ],
        'subtotal': float(subtotal),
        'vat': float(vat),
        'total': float(total),
        'has_items': bool(items),
    }
