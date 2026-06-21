# P0 — детальное руководство по реализации (код-левел)

> **Статус:** предложение, готово к реализации по шагам. Код в этом документе — скелеты,
> построенные на фактических конвенциях репозитория; перед коммитом адаптировать под
> финальные имена и прогнать валидационный гейт из `AGENTS.md`.
> **Охват:** Фаза 1 (Товарный каталог + позиции сделки), Фаза 2 (AI: транскрипция/резюме
> звонков), Фаза 3 (Двусторонняя email-почта). Карта всех 10 фаз — в
> `docs/specs/CRM_FEATURE_ROADMAP.md`.
> **Конвенции, на которые опирается код:** ninja-роутер как декоратор на общем `crm_router`
> (`apps/crm/_api_common.py`), схемы в `apps/crm/schemas.py`, feature-gating через
> `require_feature_access`/`Plan.has_feature` (`apps/core/access.py:64`), рендер документа
> через `Template`+WeasyPrint (`apps/documents/pdf.py`), конвейер сообщений
> `route_incoming_message`/`_broadcast_message` (`apps/channels/tasks.py`), клиент Exolve
> `download_record` (`apps/telephony/exolve_client.py:173`), skill `handle(args)`
> (`apps/ai_assistant/hermes_skills/`), тесты на `TenantAPITestCase`.

## Маркировка уровней проверки

В тексте используются пометки: `[локально]` — проверяется тестами/сборкой/типами;
`[граница]` — требует живого вызова внешней системы; `[сквозь]` — наблюдаемый
пользователем результат. Любой стык, помеченный `[граница]`/`[сквозь]`, в dev-среде без
боевых ключей подтверждается только по логам за один прогон.

---

# ФАЗА 1 — Товарный каталог и позиции сделки

## 1.1. Диаграмма потоков данных

```
СОЗДАНИЕ ТОВАРА
  Frontend ProductsView ──POST /api/crm/products/──► products_api.create_product
       │                                                   │
       │                                          require_crm_permission('products','create')
       │                                                   │
       └─◄── {id} ◄────────────────────────────── Product.objects.create(...)

ДОБАВЛЕНИЕ ПОЗИЦИИ В СДЕЛКУ
  DealDetailView ──POST /api/crm/deals/{id}/items/──► deal_items_api.add_item
       │                                                   │
       │                                       _scoped_object_or_error(Deal) + scope-guard
       │                                                   │
       │                                       DealItem.objects.create(snapshot цены/НДС)
       │                                                   │
       │                                       services.pricing.recalc_deal_amount(deal)
       │                                                   │  ← пересчёт Deal.amount = Σ line_total
       └─◄── {item, deal_amount} ◄────────────────────────┘

ГЕНЕРАЦИЯ СЧЁТА С ПОЗИЦИЯМИ
  DealDetailView «Сформировать счёт» ──► documents.create_document(deal, template=INVOICE)
       │                                                   │
       │                                  build_document_context(deal) ← добавляет items[]
       │                                                   │
       │                                  pdf._render_html(template.html_body, context)
       └─◄── document_id ◄──────────────────── WeasyPrint → PDF (таблица позиций)
```

## 1.2. Пошаговый чеклист задач

1. Создать модели `Product`, `ProductCategory`, `DealItem` в `apps/crm/models.py` (раздел 1.3).
2. Сгенерировать миграцию: `docker compose run --rm web python manage.py makemigrations crm`.
   Убедиться, что миграция не тянет данные (только `CreateModel`).
3. Зарегистрировать модели в `apps/crm/admin.py` по образцу существующих регистраций.
4. Добавить схемы `ProductIn/ProductPatchIn`, `DealItemIn/DealItemPatchIn` в `apps/crm/schemas.py` (раздел 1.4).
5. Расширить матрицу прав: добавить сущность `products` в `CRM_PERMISSION_ENTITIES`
   (`apps/core/access.py`) и в дефолтные профили `RolePermission` (поиск по `deals` как образцу).
6. Создать `apps/crm/products_api.py` и `apps/crm/deal_items_api.py` (раздел 1.5); подключить
   их импортом в `apps/crm/api.py` (ради side-effect декораторов, как остальные `*_api`).
7. Создать сервис пересчёта `apps/crm/services/pricing.py` (раздел 1.6).
8. Расширить контекст документа позициями: функция `build_document_context` в
   `apps/documents/services.py` (раздел 1.7) и обновить системные шаблоны счёта/оферты/акта
   в `apps/documents/seed.py` на цикл `{% for item in items %}`.
9. Добавить feature-код `catalog` и лимит `max_products` в `Plan`
   (`apps/billing/models.py` + миграция seed по образцу `0006_seed_plans_solo_komanda`).
10. Включить дефолтный провижининг (опционально — базовые единицы измерения) в
    `apps/tenants/services.py::provision_tenant`.
11. Frontend: типы и функции в `frontend/src/api/crm.ts` (раздел 1.8), `ProductsView.vue`,
    блок «Позиции» в `DealDetailView.vue`, пункт меню в `AppMenu.vue`, маршрут в роутере.
12. Тесты backend (раздел 1.9) + vitest на расчёт итога.
13. Прогнать валидационный гейт (раздел «Критерии приёмки 1.10»).

## 1.3. Модели (`apps/crm/models.py`, дописать в конец файла)

```python
class ProductCategory(models.Model):
    """Категория номенклатуры (дерево)."""
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children',
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'product categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    """Позиция каталога (товар или услуга)."""
    UNIT_CHOICES = [
        ('pcs', 'шт'), ('hour', 'час'), ('service', 'усл'),
        ('kg', 'кг'), ('month', 'мес'), ('license', 'лиц'),
    ]
    name = models.CharField(max_length=300)
    sku = models.CharField(max_length=100, blank=True, db_index=True)
    category = models.ForeignKey(
        ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products',
    )
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='pcs')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='RUB')
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20)  # процент НДС
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    custom_fields = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['sku']), models.Index(fields=['is_active', 'name'])]

    def __str__(self):
        return self.name


class DealItem(models.Model):
    """Позиция сделки. Цена/НДС/наименование — снимок на момент добавления."""
    deal = models.ForeignKey('Deal', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.PROTECT, related_name='deal_items')
    name_snapshot = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)        # снимок цены за единицу
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']

    @property
    def line_subtotal(self):
        """Сумма строки без НДС и со скидкой."""
        gross = self.price * self.quantity
        return gross * (Decimal('1') - self.discount_percent / Decimal('100'))

    @property
    def line_vat(self):
        return self.line_subtotal * self.vat_rate / Decimal('100')

    @property
    def line_total(self):
        return self.line_subtotal + self.line_vat

    def __str__(self):
        return f'{self.name_snapshot} ×{self.quantity}'
```

> Добавить вверху файла `from decimal import Decimal`. Округление — единая политика в
> сервисе пересчёта (раздел 1.6), а не в свойствах, чтобы не плодить расхождения.

## 1.4. Схемы (`apps/crm/schemas.py`, дописать в конец)

```python
# --- Catalog ----------------------------------------------------------------

class ProductIn(Schema):
    name: str
    sku: str = ''
    category_id: int | None = None
    unit: str = 'pcs'
    price: float = 0
    currency: str = 'RUB'
    vat_rate: float = 20
    description: str = ''
    is_active: bool = True
    custom_fields: dict = {}


class ProductPatchIn(Schema):
    name: str | None = None
    sku: str | None = None
    category_id: int | None = None
    unit: str | None = None
    price: float | None = None
    currency: str | None = None
    vat_rate: float | None = None
    description: str | None = None
    is_active: bool | None = None
    custom_fields: dict | None = None


class DealItemIn(Schema):
    product_id: int
    quantity: float = 1
    price: float | None = None          # None → берём текущую цену товара (снимок)
    discount_percent: float = 0
    vat_rate: float | None = None       # None → берём из товара


class DealItemPatchIn(Schema):
    quantity: float | None = None
    price: float | None = None
    discount_percent: float | None = None
    vat_rate: float | None = None
    sort_order: int | None = None
```

## 1.5. API (`apps/crm/products_api.py` и `apps/crm/deal_items_api.py`)

`apps/crm/products_api.py`:

```python
from __future__ import annotations

from apps.audit.services import log_event
from apps.core.access import require_crm_permission

from ._api_common import _ensure_builtin, _scoped_object_or_error, crm_router
from .models import Product
from .schemas import ProductIn, ProductPatchIn


def _serialize_product(p: Product) -> dict:
    return {
        'id': p.id, 'name': p.name, 'sku': p.sku, 'category_id': p.category_id,
        'unit': p.unit, 'price': float(p.price), 'currency': p.currency,
        'vat_rate': float(p.vat_rate), 'description': p.description,
        'is_active': p.is_active, 'created_at': p.created_at.isoformat(),
    }


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
    p = Product.objects.create(**payload.dict())
    log_event(request, action='create', instance=p)
    return {'id': p.id}


@crm_router.patch('/products/{product_id}/')
def patch_product(request, product_id: int, payload: ProductPatchIn):
    require_crm_permission(request, 'products', 'update')
    _ensure_builtin(request)
    p = _scoped_object_or_error(request, Product, product_id, entity='products', action='update')
    changes = payload.dict(exclude_unset=True)
    if changes:
        Product.objects.filter(id=product_id).update(**changes)
        log_event(request, action='update', instance=p)
    return {'detail': 'ok'}


@crm_router.delete('/products/{product_id}/')
def delete_product(request, product_id: int):
    require_crm_permission(request, 'products', 'delete')
    _ensure_builtin(request)
    p = _scoped_object_or_error(request, Product, product_id, entity='products', action='delete')
    log_event(request, action='delete', instance=p)
    # PROTECT на DealItem.product не даст удалить товар, использованный в сделках —
    # вместо удаления делаем is_active=False, если есть связанные позиции.
    if p.deal_items.exists():
        Product.objects.filter(id=product_id).update(is_active=False)
        return {'detail': 'archived'}
    Product.objects.filter(id=product_id).delete()
    return {'detail': 'deleted'}
```

`apps/crm/deal_items_api.py`:

```python
from __future__ import annotations

from decimal import Decimal

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
    product = Product.objects.get(id=payload.product_id)
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
    log_event(request, action='update', instance=deal,
              changes={'Позиция добавлена': {'before': '', 'after': item.name_snapshot}})
    return {'item_id': item.id, 'deal_amount': float(new_amount)}


@crm_router.patch('/deals/{deal_id}/items/{item_id}/')
def patch_deal_item(request, deal_id: int, item_id: int, payload: DealItemPatchIn):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    changes = payload.dict(exclude_unset=True)
    if changes:
        DealItem.objects.filter(id=item_id, deal_id=deal_id).update(**changes)
        recalc_deal_amount(deal)
    return {'detail': 'ok', 'deal_amount': float(deal.amount or 0)}


@crm_router.delete('/deals/{deal_id}/items/{item_id}/')
def delete_deal_item(request, deal_id: int, item_id: int):
    require_crm_permission(request, 'deals', 'update')
    _ensure_builtin(request)
    deal = _scoped_object_or_error(request, Deal, deal_id, entity='deals', action='update')
    DealItem.objects.filter(id=item_id, deal_id=deal_id).delete()
    new_amount = recalc_deal_amount(deal)
    return {'detail': 'deleted', 'deal_amount': float(new_amount)}
```

Подключение в `apps/crm/api.py` (рядом с импортом остальных доменных модулей — ради
side-effect декораторов):

```python
from . import (  # noqa: F401
    activities_api, companies_api, contacts_api, deal_items_api,
    deals_api, pipelines_api, products_api, stats_api,
)
```

## 1.6. Сервис пересчёта (`apps/crm/services/pricing.py`)

```python
"""Пересчёт суммы сделки из позиций. Единая политика округления."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from apps.crm.models import Deal

_CENTS = Decimal('0.01')


def _round(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def recalc_deal_amount(deal: Deal) -> Decimal:
    """Σ line_total по всем позициям. Если позиций нет — сумму НЕ трогаем
    (остаётся введённой вручную)."""
    items = list(deal.items.all())
    if not items:
        return deal.amount or Decimal('0')
    total = sum((item.line_total for item in items), Decimal('0'))
    total = _round(total)
    Deal.objects.filter(id=deal.id).update(amount=total)
    deal.amount = total
    return total


def serialize_deal_items(deal: Deal) -> dict:
    items = list(deal.items.select_related('product').all())
    subtotal = _round(sum((i.line_subtotal for i in items), Decimal('0')))
    vat = _round(sum((i.line_vat for i in items), Decimal('0')))
    total = _round(sum((i.line_total for i in items), Decimal('0')))
    return {
        'items': [
            {
                'id': i.id, 'product_id': i.product_id, 'name': i.name_snapshot,
                'quantity': float(i.quantity), 'price': float(i.price),
                'discount_percent': float(i.discount_percent), 'vat_rate': float(i.vat_rate),
                'line_subtotal': float(_round(i.line_subtotal)),
                'line_vat': float(_round(i.line_vat)),
                'line_total': float(_round(i.line_total)),
            }
            for i in items
        ],
        'subtotal': float(subtotal), 'vat': float(vat), 'total': float(total),
        'has_items': bool(items),
    }
```

## 1.7. Связь с документооборотом

В `apps/documents/services.py` (там, где формируется контекст для рендера — функция, которую
вызывает `pdf._render_html`) добавить позиции в контекст. Контракт переменных шаблона уже
задан `COMMON_SCHEMA` в `apps/documents/seed.py`; расширяем его ключом `items`:

```python
def build_document_context(deal) -> dict:
    from apps.crm.services.pricing import serialize_deal_items
    base = {
        'deal_id': deal.id, 'deal_name': deal.name,
        'amount': f'{deal.amount:,.2f}'.replace(',', ' ') if deal.amount else '0',
        'currency': deal.currency,
        'contact_name': str(deal.contact) if deal.contact else '',
        'company_name': deal.company.name if deal.company else '',
        'created_at': deal.created_at.isoformat(),
    }
    base.update(serialize_deal_items(deal))   # items[], subtotal, vat, total
    return base
```

Системный шаблон счёта (`apps/documents/seed.py`, запись `DocumentType.INVOICE`) переписать
табличную часть на цикл Django-template:

```html
<table style="width:100%;border-collapse:collapse">
  <tr>
    <th style="border:1px solid #ccc;padding:6px">№</th>
    <th style="border:1px solid #ccc;padding:6px">Наименование</th>
    <th style="border:1px solid #ccc;padding:6px">Кол-во</th>
    <th style="border:1px solid #ccc;padding:6px">Цена</th>
    <th style="border:1px solid #ccc;padding:6px">Сумма</th>
  </tr>
  {% for item in items %}
  <tr>
    <td style="border:1px solid #ccc;padding:6px">{{ forloop.counter }}</td>
    <td style="border:1px solid #ccc;padding:6px">{{ item.name }}</td>
    <td style="border:1px solid #ccc;padding:6px">{{ item.quantity }}</td>
    <td style="border:1px solid #ccc;padding:6px">{{ item.price }}</td>
    <td style="border:1px solid #ccc;padding:6px">{{ item.line_total }}</td>
  </tr>
  {% endfor %}
</table>
<p><strong>Итого без НДС:</strong> {{ subtotal }} {{ currency }}</p>
<p><strong>НДС:</strong> {{ vat }} {{ currency }}</p>
<p><strong>Итого к оплате:</strong> {{ total }} {{ currency }}</p>
```

> Существующий публичный контракт подписания `/sign/<token>/` не меняется — затрагивается
> только наполнение контекста и HTML системных шаблонов.

## 1.8. Frontend

`frontend/src/api/crm.ts` (дописать типы и функции по образцу существующих `api.get/post`):

```typescript
export interface CrmProduct {
  id: number; name: string; sku: string; category_id: number | null
  unit: string; price: number; currency: string; vat_rate: number
  description: string; is_active: boolean; created_at: string
}
export interface CrmDealItem {
  id: number; product_id: number; name: string; quantity: number
  price: number; discount_percent: number; vat_rate: number
  line_subtotal: number; line_vat: number; line_total: number
}
export interface CrmDealItems {
  items: CrmDealItem[]; subtotal: number; vat: number; total: number; has_items: boolean
}

export const listProducts = (q?: string) =>
  api.get<CrmProduct[]>('/crm/products/', { params: { q } })
export const createProduct = (data: Partial<CrmProduct>) =>
  api.post<{ id: number }>('/crm/products/', data)
export const patchProduct = (id: number, data: Partial<CrmProduct>) =>
  api.patch(`/crm/products/${id}/`, data)
export const deleteProduct = (id: number) => api.delete(`/crm/products/${id}/`)

export const listDealItems = (dealId: number) =>
  api.get<CrmDealItems>(`/crm/deals/${dealId}/items/`)
export const addDealItem = (dealId: number, data: { product_id: number; quantity: number; price?: number; discount_percent?: number }) =>
  api.post<{ item_id: number; deal_amount: number }>(`/crm/deals/${dealId}/items/`, data)
export const deleteDealItem = (dealId: number, itemId: number) =>
  api.delete(`/crm/deals/${dealId}/items/${itemId}/`)
```

UI-задачи:
- Новый `frontend/src/views/ProductsView.vue` — `PDataTable` со списком, диалог CRUD
  (образец — `CompaniesView.vue`); директиву `v-responsive-table` применить как в остальных таблицах.
- Маршрут в `frontend/src/router/index.ts` внутри `/app` children: `{ path: 'products', name: 'products', component: () => import('@/views/ProductsView.vue'), meta: { feature: 'catalog' } }`.
- Пункт меню в `frontend/src/layout/AppMenu.vue`: `{ to: '/app/products', label: 'Товары', icon: 'pi pi-box', feature: 'catalog' }`.
- В `DealDetailView.vue` — презентационный компонент `DealItemsBlock.vue` (родитель владеет
  состоянием и вызовами API, дочерний только отображает таблицу позиций и итог; паттерн DEC-036).

## 1.9. Тесты backend (`apps/crm/tests/test_catalog.py`)

```python
from __future__ import annotations

from decimal import Decimal

from apps.crm.models import Deal, DealItem, Pipeline, Product, Stage
from apps.crm.services.pricing import recalc_deal_amount
from apps.users.tests.base import TenantAPITestCase


class CatalogPricingTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open')
        self.deal = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.stage, currency='RUB')
        self.product = Product.objects.create(name='Товар', price=Decimal('100'), vat_rate=Decimal('20'))

    def test_recalc_sums_line_totals_with_vat(self):
        DealItem.objects.create(deal=self.deal, product=self.product, name_snapshot='Товар',
                                quantity=Decimal('2'), price=Decimal('100'), vat_rate=Decimal('20'))
        total = recalc_deal_amount(self.deal)
        # 2 × 100 = 200 без НДС; +20% = 240
        self.assertEqual(total, Decimal('240.00'))

    def test_empty_items_keeps_manual_amount(self):
        self.deal.amount = Decimal('555')
        self.deal.save(update_fields=['amount'])
        self.assertEqual(recalc_deal_amount(self.deal), Decimal('555'))

    def test_price_snapshot_independent_from_product_price_change(self):
        item = DealItem.objects.create(deal=self.deal, product=self.product, name_snapshot='Товар',
                                       quantity=Decimal('1'), price=Decimal('100'), vat_rate=Decimal('20'))
        self.product.price = Decimal('999')
        self.product.save(update_fields=['price'])
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal('100'))
```

## 1.10. Критерии приёмки Фазы 1

1. `[локально]` `manage.py check` — 0 issues; `makemigrations --check` не выявляет дрейфа;
   `ruff check .` зелёный; новые тесты `test_catalog.py` проходят.
2. `[локально]` `npm run typecheck` EXIT=0, `npm run build` EXIT=0, vitest на расчёт итога зелёный.
3. `[сквозь]` В UI: создать товар; в карточке сделки добавить две позиции — `Deal.amount`
   автоматически равен сумме строк с НДС; ручной ввод суммы при наличии позиций заблокирован.
4. `[сквозь]` Кнопка «Сформировать счёт» создаёт документ, в PDF присутствует таблица позиций
   и три строки итога (без НДС / НДС / к оплате).
5. `[сквозь]` Товар, использованный в сделке, при удалении архивируется (`is_active=False`),
   а не ломает сделку (FK `PROTECT`).
6. Обновлены `DECISIONS.md` (новый DEC), `TASK_STATE.md`, `DEV_LOG.md`,
   `RELEASE_NOTES.md` (для пользователя: «Каталог товаров и автоматический счёт»).

---

# ФАЗА 2 — AI: транскрипция и резюме звонков

> **Граница достоверности.** Эта фаза стыкуется с двумя внешними системами: распознавание
> речи (ASR) и Anthropic API. Их контракты в dev-среде без боевых ключей сквозным
> результатом не проверяются. Перед написанием интеграционного кода обязательно прочитать
> через skill `claude-api` точные id моделей и сигнатуры SDK; контракт ASR-провайдера —
> отдельным решением DEC. Скачивание записи опирается на уже реализованный
> `ExolveClient.download_record` (`apps/telephony/exolve_client.py:173`).

## 2.1. Диаграмма потоков данных

```
Call Events Exolve ──► CallRecord (record_file заполнен фоновой загрузкой, DEC-042)
        │
        │  сигнал post_save / явный вызов после загрузки записи
        ▼
  transcribe_call_record.delay(call_record_id)        [Celery]
        │
        │  ExolveClient.download_record(url) ─► bytes  (если record_file ещё не на диске)
        │            └── [граница] Bearer-аутентификация Exolve
        ▼
  ASR-провайдер: bytes → text                          [граница: внешний ASR]
        │
        ▼
  CallTranscript.objects.create(text=..., status='done')
        │
        ▼
  summarize_call.delay(transcript_id)                  [Celery]
        │
        │  Anthropic SDK: messages.create(model=…, ...) [граница: Anthropic API]
        │            └── [TODO: сверить модель/сигнатуру через skill claude-api]
        ▼
  CallSummary (резюме, договорённости, следующий шаг)
        │
        ▼
  Activity.objects.create(type='note', deal=…, body=резюме)  → виден в таймлайне
```

## 2.2. Пошаговый чеклист задач

1. Через skill `claude-api` зафиксировать актуальную модель (по умолчанию `claude-opus-4-8`)
   и точную сигнатуру вызова Anthropic SDK; записать выбор в DECISIONS как новый DEC.
2. Выбрать ASR-провайдера, прочитать его контракт целиком, записать в тот же DEC; добавить
   ключи в `.env.example`/`.env.prod.example` (паттерн DEC-045 по маппингу env).
3. Создать модели `CallTranscript`, `CallSummary` в `apps/telephony/models.py` (раздел 2.3).
4. `makemigrations telephony` + проверка отсутствия дрейфа.
5. Создать клиент ASR `apps/ai_assistant/asr_client.py` по образцу `ExolveClient`
   (изолированный класс, логирование каждого вызова, узкий `except` на сетевые ошибки).
6. Создать Celery-задачи `transcribe_call_record`, `summarize_call` в
   `apps/ai_assistant/tasks.py` (раздел 2.4); подключить их к появлению записи звонка
   (вызов `.delay()` в обработчике Call Events телефонии, где сохраняется `record_file`).
7. Добавить навыки Hermes `crm_summarize_call`, `crm_suggest_reply` в
   `apps/ai_assistant/hermes_skills/` по образцу `crm_get_deal.py` (раздел 2.5).
8. API для UI: endpoint `GET /api/ai/calls/{call_id}/summary/` и
   `POST /api/ai/chats/{session_id}/suggest-reply/` в `apps/ai_assistant/api.py`.
9. Feature-код `ai_call_intelligence` + лимит `max_ai_minutes_per_month` в `Plan`.
10. Frontend: блок «Резюме звонка» в карточке сделки, кнопка «Предложить ответ» в чате.
11. Тесты с моками внешних вызовов (раздел 2.6).
12. Валидационный гейт + фиксация границы достоверности в KNOWN_ISSUES (по образцу #23).

## 2.3. Модели (`apps/telephony/models.py`, дописать)

```python
class CallTranscript(models.Model):
    STATUS = [('pending', 'В обработке'), ('done', 'Готово'), ('failed', 'Ошибка')]
    call = models.OneToOneField('CallRecord', on_delete=models.CASCADE, related_name='transcript')
    text = models.TextField(blank=True)
    language = models.CharField(max_length=8, default='ru')
    provider = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    error = models.TextField(blank=True)
    duration_billed = models.PositiveIntegerField(default=0)  # для лимита минут
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CallSummary(models.Model):
    transcript = models.OneToOneField(CallTranscript, on_delete=models.CASCADE, related_name='summary')
    summary = models.TextField(blank=True)
    agreements = models.JSONField(default=list)   # извлечённые договорённости
    next_step = models.CharField(max_length=500, blank=True)
    model = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## 2.4. Celery-задачи (`apps/ai_assistant/tasks.py`, дописать)

```python
import logging
from celery import shared_task
from django_tenants.utils import schema_context

logger = logging.getLogger('ai_assistant.transcription')


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def transcribe_call_record(schema_name: str, call_record_id: int):
    """Скачивает запись и распознаёт речь. Внешние стыки помечены [граница]."""
    from apps.telephony.models import CallRecord, CallTranscript
    from apps.telephony.exolve_client import ExolveClient
    from apps.ai_assistant.asr_client import ASRClient

    with schema_context(schema_name):
        call = CallRecord.objects.filter(id=call_record_id).first()
        if not call or not call.record_file:
            logger.warning('transcribe: no record_file for call=%s', call_record_id)
            return
        transcript, _ = CallTranscript.objects.get_or_create(call=call)
        if transcript.status == 'done':
            return  # идемпотентность
        try:
            audio_bytes = call.record_file.read()          # запись уже на диске (DEC-042)
            text = ASRClient().transcribe(audio_bytes, language='ru')  # [граница: ASR]
            transcript.text = text
            transcript.status = 'done'
            transcript.duration_billed = call.talk_time or call.duration
            transcript.save(update_fields=['text', 'status', 'duration_billed', 'updated_at'])
            logger.info('transcribe done call=%s chars=%s', call_record_id, len(text))
            summarize_call.delay(schema_name, transcript.id)
        except Exception as exc:  # noqa: BLE001 — граница ASR: фиксируем ошибку, не глотаем
            transcript.status = 'failed'
            transcript.error = str(exc)
            transcript.save(update_fields=['status', 'error', 'updated_at'])
            logger.exception('transcribe failed call=%s', call_record_id)


@shared_task
def summarize_call(schema_name: str, transcript_id: int):
    from apps.telephony.models import CallTranscript, CallSummary
    from apps.crm.models import Activity
    from apps.ai_assistant.services import summarize_transcript_via_claude  # [граница: Anthropic]

    with schema_context(schema_name):
        transcript = CallTranscript.objects.filter(id=transcript_id).first()
        if not transcript or transcript.status != 'done' or not transcript.text:
            return
        result = summarize_transcript_via_claude(transcript.text)  # {summary, agreements, next_step, model}
        CallSummary.objects.update_or_create(
            transcript=transcript,
            defaults={
                'summary': result['summary'], 'agreements': result['agreements'],
                'next_step': result['next_step'], 'model': result['model'],
            },
        )
        deal_id = transcript.call.crm_lead_id
        if deal_id:
            Activity.objects.create(
                activity_type='note',
                deal_id=int(deal_id) if deal_id.isdigit() else None,
                title='Резюме звонка',
                body=result['summary'] + (f"\n\nСледующий шаг: {result['next_step']}" if result['next_step'] else ''),
                status='done',
            )
```

> `summarize_transcript_via_claude` — новая функция в `apps/ai_assistant/services.py`.
> Её тело пишется **только после** чтения контракта Anthropic SDK через skill `claude-api`
> (точная сигнатура `messages.create`, id модели, формат ответа). В плане сигнатура и
> id модели не утверждаются как факт — помечено `# TODO: сверить с контрактом`.

## 2.5. Навык Hermes (`apps/ai_assistant/hermes_skills/crm_summarize_call.py`)

Точно по образцу `crm_get_deal.py` (тот же bootstrap `sys.path`+`django.setup()`,
`schema_context`, структурный возврат, `# noqa: BLE001` на границе skill→Hermes):

```python
def handle(args: dict) -> dict:
    call_id = args.get('call_id', '')
    tenant_slug = args.get('tenant_slug', '')
    if not tenant_slug or not call_id:
        return {'error': 'tenant_slug and call_id are required'}
    try:
        with schema_context('public'):
            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if not tenant:
                return {'error': f'Tenant not found: {tenant_slug}'}
        with schema_context(tenant.schema_name):
            from apps.telephony.models import CallTranscript
            t = CallTranscript.objects.select_related('summary', 'call').filter(call_id=call_id).first()
            if not t:
                return {'error': 'transcript not found'}
            return {
                'call_id': call_id, 'status': t.status,
                'summary': getattr(t, 'summary', None) and t.summary.summary,
                'next_step': getattr(t, 'summary', None) and t.summary.next_step,
            }
    except Exception as e:  # noqa: BLE001 — граница skill→Hermes
        logger.exception('crm_summarize_call failed call_id=%s', call_id)
        return {'error': str(e)}
```

## 2.6. Тесты (`apps/ai_assistant/tests/test_transcription.py`)

```python
from unittest.mock import patch
from apps.telephony.models import CallRecord, CallTranscript
from apps.users.tests.base import TenantAPITestCase


class TranscriptionTest(TenantAPITestCase):
    @patch('apps.ai_assistant.asr_client.ASRClient.transcribe', return_value='Привет, по сделке всё ок')
    @patch('apps.ai_assistant.tasks.summarize_call.delay')
    def test_transcribe_creates_transcript_and_chains_summary(self, mock_sum, mock_asr):
        call = CallRecord.objects.create(call_sid='x1', direction='inbound',
                                         caller_number='+7900', called_number='+7495',
                                         started_at='2026-01-01T00:00:00Z')
        # record_file мокируется отдельно или подкладывается фикстурой
        ...
        self.assertTrue(CallTranscript.objects.filter(call=call, status='done').exists())
        mock_sum.assert_called_once()
```

> Внешние вызовы ASR и Anthropic в тестах всегда мокируются. Реальная транскрипция —
> `[граница]`, подтверждается на проде по логам `ai_assistant.transcription` за один прогон.

## 2.7. Критерии приёмки Фазы 2

1. `[локально]` Миграции без дрейфа; `ruff` зелёный; тесты с моками проходят; typecheck/build зелёные.
2. `[локально]` Задача `transcribe_call_record` идемпотентна (повторный вызов при `status='done'`
   не создаёт дубль и не списывает минуты второй раз) — покрыто тестом.
3. `[граница]` На проде с боевым ASR-ключом: запись звонка распознаётся, в логах
   `transcribe done call=… chars=…`.
4. `[сквозь]` В карточке сделки после звонка появляется активность «Резюме звонка» с текстом
   и следующим шагом; навык `crm_summarize_call` возвращает резюме в чате ассистента.
5. Лимит `max_ai_minutes_per_month` уменьшается на длительность распознанного звонка; при
   достижении лимита транскрипция не запускается.
6. Граница достоверности (ASR + Anthropic) зафиксирована в KNOWN_ISSUES по образцу #23;
   обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# ФАЗА 3 — Двусторонняя email-почта как канал

> **Граница достоверности.** IMAP-приём и SMTP-отправку с реальным ящиком в dev-среде
> сквозным результатом не проверить. Перед кодом прочитать RFC 3501 и поведение `imaplib`
> (часть стандартной библиотеки Python — установленный исходник доступен). SMTP-транспорт
> уже сконфигурирован в проекте (DEC-045), переиспользуется с per-channel учётными данными.

## 3.1. Диаграмма потоков данных

```
ВХОДЯЩЕЕ ПИСЬМО
  Celery-beat poll_email_channels (каждые N минут)
        │
        │  для каждого MessengerChannel(channel_type='email', is_active):
        ▼
  imaplib.IMAP4_SSL(host).login().select('INBOX')      [граница: IMAP-сервер]
        │  search UNSEEN → fetch → email.message_from_bytes
        ▼
  дедуп по Message-ID (MessageLog.external_message_id)
        │  (новое?)
        ▼
  ChatSession.get_or_create(channel, external_chat_id=from_email)
        │
        ▼
  MessageLog.objects.create(direction='in', text=plain_body, external_message_id=msgid)
        │
        ├─► _auto_create_lead(...)  (если channel.auto_create_lead) ← переиспользуем из channels
        │
        └─► _broadcast_message(tenant_slug, channel_id, session, message)  → WS push (DEC-019)

ИСХОДЯЩЕЕ ПИСЬМО (ответ из CRM)
  ChatsView «отправить» ──POST /api/channels/{id}/send/──► route_outgoing_message.delay
        │
        ▼
  EmailBackend(per-channel SMTP creds).send_messages([EmailMessage])  [граница: SMTP]
        │
        ▼
  MessageLog.objects.create(direction='out', delivered=True/False)
```

## 3.2. Пошаговый чеклист задач

1. Добавить тип канала `('email', 'Электронная почта')` в `CHANNEL_TYPE_CHOICES`
   (`apps/channels/models.py:8`). Миграция не нужна для `choices` (только для новых полей).
2. Определить формат `credentials` для email-канала (раздел 3.3) — хранится в существующем
   `EncryptedJSONField`, новых полей модели не требуется.
3. Создать приёмник `apps/channels/email_poller.py` (раздел 3.4) — отдельный модуль,
   изолирующий стык с `imaplib`.
4. Создать Celery-beat задачу `poll_email_channels` в `apps/channels/tasks.py` (раздел 3.5);
   зарегистрировать расписание в настройках beat (там же, где остальные периодические задачи).
5. Реализовать отправку: ветка `email` в `route_outgoing_message` (`apps/channels/tasks.py:244`)
   — построить `EmailMessage` через `get_connection` с per-channel SMTP (раздел 3.6).
6. Нормализацию входящего письма свести к существующему пути `MessageLog` + `_auto_create_lead`
   + `_broadcast_message` (переиспользование, не новый конвейер).
7. Frontend: в `ChannelsView` (вкладка «Мессенджеры» в Настройках) добавить форму создания
   email-канала с полями IMAP/SMTP; иконка письма; в `ChatsView` email-канал отображается
   как остальные (компонент уже презентационный).
8. Feature/лимит: email учитывается существующим `max_inbound_channels` (тарифы v2, DEC-041) —
   новый feature-код не обязателен.
9. Тесты с моком `imaplib` и SMTP (раздел 3.7).
10. Валидационный гейт + фиксация границы достоверности в KNOWN_ISSUES.

## 3.3. Формат `credentials` email-канала

```jsonc
{
  "imap_host": "imap.beget.com", "imap_port": 993, "imap_ssl": true,
  "smtp_host": "smtp.beget.com", "smtp_port": 465, "smtp_ssl": true,
  "username": "sales@example.com",
  "password": "***",                  // шифруется EncryptedJSONField
  "poll_folder": "INBOX",
  "from_name": "Отдел продаж"
}
```

> Значения провайдера (Beget/Yandex/Gmail) в плане не предполагаются — берутся из формы
> канала. OAuth-флоу для Gmail/Yandex — отдельная задача после базовой версии (по образцу
> ограничений первой версии VK-канала, KNOWN_ISSUES #22).

## 3.4. IMAP-приёмник (`apps/channels/email_poller.py`)

```python
"""IMAP-приём для email-каналов. Изолирует стык со стандартным imaplib.
Контракт: RFC 3501 + поведение imaplib (установленный исходник стандартной библиотеки)."""
from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header, make_header

logger = logging.getLogger('channels.email')


def _decode(value: str | None) -> str:
    if not value:
        return ''
    return str(make_header(decode_header(value)))


def _extract_plain_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain' and 'attachment' not in str(part.get('Content-Disposition', '')):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
        return ''
    payload = msg.get_payload(decode=True)
    return payload.decode(msg.get_content_charset() or 'utf-8', errors='replace') if payload else ''


def fetch_new_messages(creds: dict) -> list[dict]:
    """Возвращает список нормализованных входящих: {message_id, from_email, from_name, subject, text}.
    Стык [граница]: реальный IMAP-сервер; в тестах imaplib мокируется."""
    host, port = creds['imap_host'], int(creds.get('imap_port', 993))
    box = imaplib.IMAP4_SSL(host, port) if creds.get('imap_ssl', True) else imaplib.IMAP4(host, port)
    out: list[dict] = []
    try:
        box.login(creds['username'], creds['password'])
        box.select(creds.get('poll_folder', 'INBOX'))
        typ, data = box.search(None, 'UNSEEN')
        if typ != 'OK':
            return out
        for num in data[0].split():
            typ, msg_data = box.fetch(num, '(RFC822)')
            if typ != 'OK' or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            from_raw = _decode(msg.get('From'))
            from_email = email.utils.parseaddr(from_raw)[1]
            out.append({
                'message_id': (msg.get('Message-ID') or '').strip(),
                'from_email': from_email,
                'from_name': email.utils.parseaddr(from_raw)[0] or from_email,
                'subject': _decode(msg.get('Subject')),
                'text': _extract_plain_text(msg),
            })
        logger.info('email poll host=%s user=%s new=%s', host, creds['username'], len(out))
    finally:
        try:
            box.logout()
        except Exception:  # noqa: BLE001 — закрытие соединения не должно ронять задачу
            logger.warning('imap logout failed for %s', creds.get('username'))
    return out
```

## 3.5. Beat-задача приёма (`apps/channels/tasks.py`, дописать)

```python
@shared_task
def poll_email_channels():
    """Обходит все email-каналы во всех тенантах. Beat-расписание — каждые 2–5 минут."""
    from django_tenants.utils import schema_context, get_tenant_model
    from .email_poller import fetch_new_messages

    for tenant in get_tenant_model().objects.exclude(schema_name='public'):
        with schema_context(tenant.schema_name):
            channels = MessengerChannel.objects.filter(channel_type='email', is_active=True)
            for channel in channels:
                try:
                    messages = fetch_new_messages(channel.credentials)  # [граница: IMAP]
                except Exception as exc:  # noqa: BLE001 — граница IMAP: фиксируем, не глотаем
                    channel.status, channel.status_detail = 'error', str(exc)
                    channel.save(update_fields=['status', 'status_detail'])
                    logger.exception('email poll failed channel=%s', channel.id)
                    continue
                for m in messages:
                    _ingest_email_message(tenant.schema_name, channel, m)


def _ingest_email_message(tenant_slug: str, channel: MessengerChannel, m: dict):
    if m['message_id'] and MessageLog.objects.filter(external_message_id=m['message_id']).exists():
        return  # дедуп по Message-ID
    session, _ = ChatSession.objects.get_or_create(
        channel=channel, external_chat_id=m['from_email'],
        defaults={'external_user_name': m['from_name']},
    )
    message = MessageLog.objects.create(
        chat_session=session, direction='in',
        text=f"{m['subject']}\n\n{m['text']}".strip(),
        external_message_id=m['message_id'],
    )
    if channel.auto_create_lead:
        normalized = {'name': m['from_name'], 'email': m['from_email'], 'text': m['text']}
        _auto_create_lead(channel, session, message, normalized, m['from_email'])
    _broadcast_message(tenant_slug, channel.id, session, message)
```

## 3.6. Отправка (ветка в `route_outgoing_message`)

```python
def _send_email_reply(channel: MessengerChannel, session: ChatSession, text: str) -> tuple[bool, str]:
    from django.core.mail import EmailMessage, get_connection
    creds = channel.credentials
    try:
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=creds['smtp_host'], port=int(creds.get('smtp_port', 465)),
            username=creds['username'], password=creds['password'],
            use_ssl=bool(creds.get('smtp_ssl', True)),
            use_tls=not bool(creds.get('smtp_ssl', True)),
        )
        msg = EmailMessage(
            subject='Re: обращение',
            body=text,
            from_email=f"{creds.get('from_name','')} <{creds['username']}>",
            to=[session.external_chat_id],
            connection=connection,
        )
        sent = msg.send()  # [граница: SMTP]
        return bool(sent), ''
    except Exception as exc:  # noqa: BLE001 — граница SMTP
        logger.exception('email reply failed channel=%s', channel.id)
        return False, str(exc)
```

## 3.7. Тесты (`apps/channels/tests/test_email_channel.py`)

```python
from unittest.mock import patch
from apps.channels.models import MessageLog, MessengerChannel
from apps.users.tests.base import TenantAPITestCase

NEW = [{'message_id': '<a@x>', 'from_email': 'c@e.com', 'from_name': 'Клиент',
        'subject': 'Вопрос', 'text': 'Здравствуйте'}]


class EmailIngestTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.channel = MessengerChannel.objects.create(
            name='Почта', channel_type='email', auto_create_lead=False,
            credentials={'imap_host': 'h', 'username': 'u', 'password': 'p'})

    @patch('apps.channels.tasks._broadcast_message')
    @patch('apps.channels.email_poller.fetch_new_messages', return_value=NEW)
    def test_ingest_creates_message_and_dedups(self, _fetch, _bc):
        from apps.channels.tasks import _ingest_email_message
        _ingest_email_message('test', self.channel, NEW[0])
        _ingest_email_message('test', self.channel, NEW[0])  # повтор
        self.assertEqual(MessageLog.objects.filter(external_message_id='<a@x>').count(), 1)
```

## 3.8. Критерии приёмки Фазы 3

1. `[локально]` Миграция на `choices` не требуется/без дрейфа; `ruff` зелёный; тест дедупа
   проходит; typecheck/build зелёные.
2. `[локально]` Повторный опрос того же письма не создаёт дубль `MessageLog` (тест).
3. `[граница]` На реальном ящике: задача `poll_email_channels` забирает новое письмо, в логах
   `email poll host=… new=N`; при неверных кредах канал переходит в `status='error'` с детализацией.
4. `[сквозь]` Входящее письмо появляется в `ChatsView` как сообщение; при `auto_create_lead`
   создаётся сделка; ответ из CRM уходит на адрес отправителя и сохраняется как `direction='out'`.
5. Изоляция тенантов: письма одного тенанта не видны в WS-группе другого (группа включает
   `tenant_slug`, DEC-019).
6. Граница достоверности (IMAP/SMTP с реальным ящиком) зафиксирована в KNOWN_ISSUES;
   обновлены DECISIONS/TASK_STATE/DEV_LOG/RELEASE_NOTES.

---

# Общий порядок реализации и валидации

1. Фазы P0 независимы и могут вестись параллельно разными ветками; внутри фазы порядок —
   строго по чеклисту (модели → миграция → API/сервис → фронтенд → тесты).
2. Каждый внешний стык (`[граница]`/`[сквозь]`) изолирован в отдельном модуле-клиенте
   (`asr_client.py`, `email_poller.py`) и до написания кода требует чтения контракта целиком.
3. Гейт завершения каждой фазы: `docker compose down && up -d --build`,
   `manage.py check` (0 issues), `makemigrations --check` (без дрейфа), `ruff check .`,
   целевые backend-тесты, `npm run typecheck`/`build`/`test`, ручная HTTP-проверка экранов.
4. Update Ritual (`AGENTS.md`): новый DEC на каждую фазу, статус в TASK_STATE, запись в
   DEV_LOG (дата/файлы/валидация/риски), KNOWN_ISSUES для зафиксированных границ достоверности,
   RELEASE_NOTES на русском для видимых пользователю изменений.
5. Коммит и индексацию выполняет пользователь; агент останавливается после прохождения гейта.
```
