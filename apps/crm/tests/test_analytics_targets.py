from __future__ import annotations

import json
from datetime import timedelta

from django.utils import timezone

from apps.crm.models import Deal, Pipeline, SalesTarget, Stage
from apps.users.tests.base import TenantAPITestCase


class AnalyticsBaseTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='an_owner@example.com', username='an_owner')
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True)
        self.s_open = Stage.objects.create(pipeline=self.pipeline, name='Открыта', stage_type='open', sort_order=0)
        self.s_won = Stage.objects.create(pipeline=self.pipeline, name='Выиграна', stage_type='won', sort_order=1)
        self.s_lost = Stage.objects.create(pipeline=self.pipeline, name='Проиграна', stage_type='lost', sort_order=2)

    def _deal(self, stage, amount=None, **kw):
        return Deal.objects.create(name='D', pipeline=self.pipeline, stage=stage, responsible=self.owner,
                                   amount=amount, **kw)


class ClosedAtTest(AnalyticsBaseTest):
    def test_move_to_won_sets_closed_at_and_back_clears(self):
        deal = self._deal(self.s_open, amount=1000)
        self.assertIsNone(deal.closed_at)

        resp = self.client.patch(
            f'/api/crm/deals/{deal.id}/move/',
            data=json.dumps({'stage_id': self.s_won.id}),
            content_type='application/json',
            **self.auth_headers(self.owner),
        )
        self.assertEqual(resp.status_code, 200)
        deal.refresh_from_db()
        self.assertIsNotNone(deal.closed_at)

        # возврат в работу обнуляет closed_at
        self.client.patch(
            f'/api/crm/deals/{deal.id}/move/',
            data=json.dumps({'stage_id': self.s_open.id}),
            content_type='application/json',
            **self.auth_headers(self.owner),
        )
        deal.refresh_from_db()
        self.assertIsNone(deal.closed_at)


class FunnelLossForecastTest(AnalyticsBaseTest):
    def test_funnel_winrate_and_shares(self):
        self._deal(self.s_open, amount=100)
        self._deal(self.s_won, amount=200, closed_at=timezone.now())
        self._deal(self.s_lost, amount=50, closed_at=timezone.now())
        resp = self.client.get(f'/api/crm/analytics/funnel/?pipeline_id={self.pipeline.id}', **self.auth_headers(self.owner))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['summary']['total'], 3)
        self.assertEqual(data['summary']['won'], 1)
        self.assertEqual(data['summary']['lost'], 1)
        # win_rate = won / (won + lost) = 1/2 = 50%
        self.assertEqual(data['summary']['win_rate'], 50.0)
        self.assertEqual(len(data['stages']), 3)

    def test_loss_reasons_grouping(self):
        self._deal(self.s_lost, amount=100, loss_reason='Дорого', closed_at=timezone.now())
        self._deal(self.s_lost, amount=200, loss_reason='Дорого', closed_at=timezone.now())
        self._deal(self.s_lost, amount=50, loss_reason='', closed_at=timezone.now())
        resp = self.client.get('/api/crm/analytics/loss-reasons/', **self.auth_headers(self.owner))
        rows = resp.json()
        by_reason = {r['loss_reason']: r for r in rows}
        self.assertEqual(by_reason['Дорого']['count'], 2)
        self.assertEqual(by_reason['Дорого']['amount'], 300.0)
        self.assertIn('Не указана', by_reason)

    def test_forecast_open_and_period(self):
        today = timezone.localdate()
        self._deal(self.s_open, amount=500, expected_close_date=today)
        self._deal(self.s_open, amount=300, expected_close_date=today + timedelta(days=60))
        d_from = today.isoformat()
        d_to = (today + timedelta(days=7)).isoformat()
        resp = self.client.get(f'/api/crm/analytics/forecast/?date_from={d_from}&date_to={d_to}', **self.auth_headers(self.owner))
        data = resp.json()
        self.assertEqual(data['open_total_amount'], 800.0)
        self.assertEqual(data['open_count'], 2)
        self.assertEqual(data['period_forecast_amount'], 500.0)
        self.assertEqual(data['period_forecast_count'], 1)


class SalesTargetTest(AnalyticsBaseTest):
    def test_upsert_creates_then_updates_same_row(self):
        period = timezone.localdate().strftime('%Y-%m')
        payload = {'period': period, 'responsible_id': self.owner.id, 'target_amount': 100000, 'target_count': 5}
        r1 = self.client.post('/api/crm/targets/', data=json.dumps(payload),
                              content_type='application/json', **self.auth_headers(self.owner))
        self.assertEqual(r1.status_code, 200)
        payload['target_amount'] = 200000
        r2 = self.client.post('/api/crm/targets/', data=json.dumps(payload),
                              content_type='application/json', **self.auth_headers(self.owner))
        self.assertEqual(r2.json()['id'], r1.json()['id'])  # тот же план (upsert)
        self.assertEqual(SalesTarget.objects.count(), 1)
        self.assertEqual(float(SalesTarget.objects.get().target_amount), 200000.0)

    def test_target_progress_actual_vs_plan(self):
        start = timezone.localdate().replace(day=1)
        SalesTarget.objects.create(period_month=start, responsible=self.owner, target_amount=1000, target_count=4)
        # два выигранных в этом месяце
        self._deal(self.s_won, amount=600, closed_at=timezone.now())
        self._deal(self.s_won, amount=300, closed_at=timezone.now())
        period = start.strftime('%Y-%m')
        resp = self.client.get(f'/api/crm/analytics/target-progress/?period={period}', **self.auth_headers(self.owner))
        rows = resp.json()
        row = next(r for r in rows if r['responsible_id'] == self.owner.id)
        self.assertEqual(row['actual_amount'], 900.0)
        self.assertEqual(row['actual_count'], 2)
        self.assertEqual(row['amount_pct'], 90.0)
        self.assertEqual(row['count_pct'], 50.0)

    def test_targets_forbidden_for_manager(self):
        manager = self.create_user(role='manager', email='an_mgr@example.com', username='an_mgr')
        resp = self.client.get('/api/crm/targets/', **self.auth_headers(manager))
        self.assertEqual(resp.status_code, 403)
