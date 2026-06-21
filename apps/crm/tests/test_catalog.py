from __future__ import annotations

from decimal import Decimal

from apps.crm.models import Deal, DealItem, Pipeline, Product, Stage
from apps.crm.services.pricing import recalc_deal_amount, serialize_deal_items
from apps.users.tests.base import TenantAPITestCase


class CatalogPricingTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0)
        self.stage = Stage.objects.create(
            pipeline=self.pipeline, name='New', stage_type='open', sort_order=0,
        )
        self.deal = Deal.objects.create(
            name='D', pipeline=self.pipeline, stage=self.stage, currency='RUB',
        )
        self.product = Product.objects.create(
            name='Товар', price=Decimal('100'), vat_rate=Decimal('20'),
        )

    def test_recalc_sums_line_totals_with_vat(self):
        DealItem.objects.create(
            deal=self.deal, product=self.product, name_snapshot='Товар',
            quantity=Decimal('2'), price=Decimal('100'), vat_rate=Decimal('20'),
        )
        total = recalc_deal_amount(self.deal)
        # 2 × 100 = 200 без НДС; +20% = 240.00
        self.assertEqual(total, Decimal('240.00'))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal('240.00'))

    def test_discount_applied_before_vat(self):
        DealItem.objects.create(
            deal=self.deal, product=self.product, name_snapshot='Товар',
            quantity=Decimal('1'), price=Decimal('100'),
            discount_percent=Decimal('10'), vat_rate=Decimal('20'),
        )
        total = recalc_deal_amount(self.deal)
        # 100 − 10% = 90; +20% = 108.00
        self.assertEqual(total, Decimal('108.00'))

    def test_empty_items_keeps_manual_amount(self):
        self.deal.amount = Decimal('555')
        self.deal.save(update_fields=['amount'])
        self.assertEqual(recalc_deal_amount(self.deal), Decimal('555'))

    def test_price_snapshot_independent_from_product_price_change(self):
        item = DealItem.objects.create(
            deal=self.deal, product=self.product, name_snapshot='Товар',
            quantity=Decimal('1'), price=Decimal('100'), vat_rate=Decimal('20'),
        )
        self.product.price = Decimal('999')
        self.product.save(update_fields=['price'])
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal('100'))

    def test_serialize_deal_items_totals(self):
        DealItem.objects.create(
            deal=self.deal, product=self.product, name_snapshot='Товар',
            quantity=Decimal('2'), price=Decimal('100'), vat_rate=Decimal('20'),
        )
        data = serialize_deal_items(self.deal)
        self.assertTrue(data['has_items'])
        self.assertEqual(data['subtotal'], 200.0)
        self.assertEqual(data['vat'], 40.0)
        self.assertEqual(data['total'], 240.0)
        self.assertEqual(len(data['items']), 1)

    def test_document_context_includes_items(self):
        from apps.documents.mapping import _extract_data_from_deal

        DealItem.objects.create(
            deal=self.deal, product=self.product, name_snapshot='Товар',
            quantity=Decimal('1'), price=Decimal('100'), vat_rate=Decimal('20'),
        )
        context = _extract_data_from_deal(self.deal)
        self.assertIn('items', context)
        self.assertEqual(len(context['items']), 1)
        self.assertEqual(context['total'], 120.0)
