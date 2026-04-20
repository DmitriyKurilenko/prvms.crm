from __future__ import annotations

from django.utils import timezone

from apps.crm.models import Activity, Deal, Pipeline, Stage
from apps.crm.services.auto_actions import process_stage_change
from apps.users.tests.base import TenantAPITestCase


class CRMAutoActionsTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.manager_user = self.create_user(role='manager', email='crm_manager@example.com', username='crm_manager')
        self.pipeline = Pipeline.objects.create(name='Main', is_default=True, sort_order=0, is_active=True)
        self.old_stage = Stage.objects.create(
            pipeline=self.pipeline,
            name='Old',
            stage_type='open',
            sort_order=0,
            auto_action={},
        )
        self.new_stage = Stage.objects.create(
            pipeline=self.pipeline,
            name='New',
            stage_type='open',
            sort_order=1,
            auto_action={'type': 'create_task', 'title': 'Follow up', 'days_offset': 2},
        )
        self.deal = Deal.objects.create(
            name='AutoAction Deal',
            pipeline=self.pipeline,
            stage=self.old_stage,
            responsible=self.manager_user,
            amount=1000,
            currency='RUB',
            source='manual',
        )

    def test_create_task_auto_action_sets_created_by_from_responsible_user(self):
        process_stage_change(self.deal, self.old_stage, self.new_stage)

        task = Activity.objects.get(activity_type='task', deal=self.deal)
        self.assertEqual(task.title, 'Follow up')
        self.assertEqual(task.responsible_id, self.manager_user.id)
        self.assertEqual(task.created_by_id, self.manager_user.id)
        self.assertTrue(task.due_date > timezone.now())
