from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.crm.models import Activity, Deal, Pipeline, Stage
from apps.crm.services.maintenance import backfill_closed_at
from apps.users.tests.base import TenantAPITestCase


class BackfillClosedAtTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0)
        self.open = Stage.objects.create(pipeline=self.pipeline, name='Open', stage_type='open', sort_order=0)
        self.won = Stage.objects.create(pipeline=self.pipeline, name='Won', stage_type='won', sort_order=1)
        self.lost = Stage.objects.create(pipeline=self.pipeline, name='Lost', stage_type='lost', sort_order=2)

    def test_backfill_uses_last_stage_change(self):
        deal = Deal.objects.create(name='D', pipeline=self.pipeline, stage=self.won)
        moment = timezone.now() - timedelta(days=4)
        act = Activity.objects.create(activity_type='stage_change', deal=deal, title='moved', status='done')
        Activity.objects.filter(id=act.id).update(created_at=moment)

        self.assertEqual(backfill_closed_at(), 1)
        deal.refresh_from_db()
        self.assertIsNotNone(deal.closed_at)
        self.assertAlmostEqual(deal.closed_at, moment, delta=timedelta(seconds=1))

    def test_backfill_falls_back_to_updated_at(self):
        deal = Deal.objects.create(name='D2', pipeline=self.pipeline, stage=self.lost)
        self.assertEqual(backfill_closed_at(), 1)
        deal.refresh_from_db()
        self.assertIsNotNone(deal.closed_at)
        self.assertAlmostEqual(deal.closed_at, deal.updated_at, delta=timedelta(seconds=1))

    def test_open_deal_untouched(self):
        deal = Deal.objects.create(name='D3', pipeline=self.pipeline, stage=self.open)
        backfill_closed_at()
        deal.refresh_from_db()
        self.assertIsNone(deal.closed_at)

    def test_idempotent(self):
        existing = timezone.now() - timedelta(days=10)
        deal = Deal.objects.create(name='D4', pipeline=self.pipeline, stage=self.won, closed_at=existing)
        self.assertEqual(backfill_closed_at(), 0)
        deal.refresh_from_db()
        self.assertAlmostEqual(deal.closed_at, existing, delta=timedelta(seconds=1))
