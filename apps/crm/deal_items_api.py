from __future__ import annotations

from decimal import Decimal

from ninja.errors import HttpError

from apps.audit.services import log_event
from apps.core.access import require_crm_permission

from ._api_common import _ensure_builtin, _scoped_object_or_error, crm_router
from .models import Deal, DealItem, Product
from .schemas import DealItemIn, DealItemPatchIn
from .services.pricing import recalc_deal_amount, serialize_deal_items


@crm_router.get('/deals/{deal_id}/items/')
def list_deal_items(request, deal_id: int):
    require_crm_permission(request, 'deals', 'view')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='view')
    return serialize_deal_items(deal)


@crm_router.post('/deals/{deal_id}/items/')
def add_deal_item(request, deal_id: int, payload: DealItemIn):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    product = Product.objects.filter(id=payload.product_id).first()
    if product is None:
        raise HttpError(404, 'Product not found')
    item = DealItem.objects.create(
        deal=deal,
        product=product,
        name_snapshot=product.name,
        quantity=Decimal(str(payload.quantity)),
        price=Decimal(str(payload.price)) if payload.price is not None else product.price,
        discount_percent=Decimal(str(payload.discount_percent)),
        vat_rate=Decimal(str(payload.vat_rate)) if payload.vat_rate is not None else product.vat_rate,
    )
    new_amount = recalc_deal_amount(deal)
    log_event(
        request,
        action='update',
        instance=deal,
        changes={'Позиция добавлена': {'before': '', 'after': item.name_snapshot}},
    )
    return {'item_id': item.id, 'deal_amount': float(new_amount)}


@crm_router.patch('/deals/{deal_id}/items/{item_id}/')
def patch_deal_item(request, deal_id: int, item_id: int, payload: DealItemPatchIn):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    if not DealItem.objects.filter(id=item_id, deal_id=deal_id).exists():
        raise HttpError(404, 'Item not found')
    changes = payload.dict(exclude_unset=True)
    if changes:
        DealItem.objects.filter(id=item_id, deal_id=deal_id).update(**changes)
    new_amount = recalc_deal_amount(deal)
    return {'detail': 'ok', 'deal_amount': float(new_amount)}


@crm_router.delete('/deals/{deal_id}/items/{item_id}/')
def delete_deal_item(request, deal_id: int, item_id: int):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    DealItem.objects.filter(id=item_id, deal_id=deal_id).delete()
    new_amount = recalc_deal_amount(deal)
    return {'detail': 'deleted', 'deal_amount': float(new_amount)}
