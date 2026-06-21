from __future__ import annotations

from ninja.errors import HttpError

from apps.audit.services import log_event
from apps.core.access import require_crm_permission

from ._api_common import _ensure_builtin, crm_router
from .models import Product
from .schemas import ProductIn, ProductPatchIn


def _serialize_product(p: Product) -> dict:
    return {
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'category_id': p.category_id,
        'unit': p.unit,
        'price': float(p.price),
        'currency': p.currency,
        'vat_rate': float(p.vat_rate),
        'description': p.description,
        'is_active': p.is_active,
        'created_at': p.created_at.isoformat(),
    }


def _get_product_or_404(product_id: int) -> Product:
    # Каталог — общеорганизационный ресурс без владельца, поэтому scope-фильтрация
    # (own/team) к нему неприменима. Доступ контролируется только action-флагом
    # через require_crm_permission в каждом обработчике.
    product = Product.objects.filter(id=product_id).first()
    if product is None:
        raise HttpError(404, 'Not found')
    return product


@crm_router.get('/products/')
def list_products(request, q: str | None = None, is_active: bool | None = None):
    require_crm_permission(request, 'products', 'view')
    _ensure_builtin(request)
    qs = Product.objects.all().order_by('-created_at')
    if q:
        qs = qs.filter(name__icontains=q)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return [_serialize_product(p) for p in qs]


@crm_router.post('/products/')
def create_product(request, payload: ProductIn):
    require_crm_permission(request, 'products', 'create')
    _ensure_builtin(request)
    product = Product.objects.create(**payload.dict())
    log_event(request, action='create', instance=product)
    return {'id': product.id}


@crm_router.get('/products/{product_id}/')
def get_product(request, product_id: int):
    require_crm_permission(request, 'products', 'view')
    _ensure_builtin(request)
    return _serialize_product(_get_product_or_404(product_id))


@crm_router.patch('/products/{product_id}/')
def patch_product(request, product_id: int, payload: ProductPatchIn):
    require_crm_permission(request, 'products', 'update')
    _ensure_builtin(request)
    product = _get_product_or_404(product_id)
    changes = payload.dict(exclude_unset=True)
    if changes:
        Product.objects.filter(id=product_id).update(**changes)
        log_event(request, action='update', instance=product)
    return {'detail': 'ok'}


@crm_router.delete('/products/{product_id}/')
def delete_product(request, product_id: int):
    require_crm_permission(request, 'products', 'delete')
    _ensure_builtin(request)
    product = _get_product_or_404(product_id)
    log_event(request, action='delete', instance=product)
    # FK DealItem.product=PROTECT: товар, использованный в сделках, не удаляем,
    # а архивируем, чтобы не разрушить историю позиций.
    if product.deal_items.exists():
        Product.objects.filter(id=product_id).update(is_active=False)
        return {'detail': 'archived'}
    Product.objects.filter(id=product_id).delete()
    return {'detail': 'deleted'}
