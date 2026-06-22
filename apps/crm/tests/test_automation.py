from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.crm.models import Activity, AutomationRule, Deal, Pipeline, Stage
from apps.crm.services.auto_actions import evaluate_event_rules
from apps.crm.tasks import evaluate_time_rules
from apps.users.tests.base import TenantAPITestCase


class AutomationTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(role='manager', email='auto_mgr@example.com', username='auto_mgr')
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0)
        self.stage = Stage.objects.create(pipeline=self.pipeline, name='New', stage_type='open', sort_order=0)

    def _deal(self, **kw):
        return Deal.objects.create(
            name='D', pipeline=self.pipeline, stage=self.stage, responsible=self.user, **kw,
        )

    def test_event_rule_creates_task_on_new_deal(self):
        AutomationRule.objects.create(
            name='Приветствие', trigger='new_deal', conditions={},
            action={'type': 'create_task', 'title': 'Перезвонить', 'days_offset': 1},
        )
        deal = self._deal()
        fired = evaluate_event_rules('new_deal', deal)
        self.assertEqual(fired, 1)
        task = Activity.objects.get(activity_type='task', deal=deal)
        self.assertEqual(task.title, 'Перезвонить')

    def test_event_rule_respects_pipeline_condition(self):
        other = Pipeline.objects.create(name='Other', sort_order=1)
        AutomationRule.objects.create(
            name='Только Other', trigger='new_deal', conditions={'pipeline_id': other.id},
            action={'type': 'create_task', 'title': 'X'},
        )
        deal = self._deal()  # pipeline = Main, не Other
        self.assertEqual(evaluate_event_rules('new_deal', deal), 0)
        self.assertFalse(Activity.objects.filter(activity_type='task', deal=deal).exists())

    def test_time_rule_no_activity_fires_once(self):
        rule = AutomationRule.objects.create(
            name='Висит', trigger='no_activity', conditions={'days': 3},
            action={'type': 'create_task', 'title': 'Реанимировать'},
        )
        deal = self._deal()
        # Состарим сделку: created_at в прошлом (поле auto_now_add — обновим явно).
        Deal.objects.filter(id=deal.id).update(created_at=timezone.now() - timedelta(days=5))

        evaluate_time_rules()
        self.assertEqual(Activity.objects.filter(activity_type='task', deal=deal).count(), 1)
        self.assertTrue(rule.runs.filter(deal=deal).exists())

        evaluate_time_rules()  # повтор — идемпотентно
        self.assertEqual(Activity.objects.filter(activity_type='task', deal=deal).count(), 1)

    def test_process_stage_change_still_works(self):
        # Регрессия: обёртка над execute_action сохраняет поведение stage auto_action.
        from apps.crm.services.auto_actions import process_stage_change
        new_stage = Stage.objects.create(
            pipeline=self.pipeline, name='Next', stage_type='open', sort_order=1,
            auto_action={'type': 'create_task', 'title': 'Follow up', 'days_offset': 2},
        )
        deal = self._deal()
        process_stage_change(deal, self.stage, new_stage)
        task = Activity.objects.get(activity_type='task', deal=deal)
        self.assertEqual(task.title, 'Follow up')
        self.assertEqual(task.created_by_id, self.user.id)
