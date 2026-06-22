from __future__ import annotations

import json
from datetime import timedelta

from django.utils import timezone

from apps.crm.models import Activity
from apps.crm.services.recurrence import next_occurrence
from apps.notifications.models import Notification
from apps.users.tests.base import TenantAPITestCase


class RecurrenceServiceTest(TenantAPITestCase):
    def test_weekly_next_occurrence(self):
        base = timezone.now().replace(microsecond=0)
        nxt = next_occurrence(base, 'FREQ=WEEKLY')
        self.assertIsNotNone(nxt)
        self.assertEqual((nxt - base).days, 7)

    def test_no_rule_returns_none(self):
        self.assertIsNone(next_occurrence(timezone.now(), ''))

    def test_exhausted_series_returns_none(self):
        # COUNT=1 → серия из одного вхождения, следующего нет.
        self.assertIsNone(next_occurrence(timezone.now(), 'FREQ=DAILY;COUNT=1'))

    def test_invalid_rule_returns_none(self):
        self.assertIsNone(next_occurrence(timezone.now(), 'НЕ-RRULE'))


class RecurringTaskApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='cal_owner@example.com', username='cal_owner')

    def _patch_status_done(self, task_id):
        return self.client.patch(
            f'/api/crm/activities/{task_id}/',
            data=json.dumps({'status': 'done'}),
            content_type='application/json',
            **self.auth_headers(self.owner),
        )

    def test_completing_recurring_task_spawns_next(self):
        due = timezone.now().replace(microsecond=0)
        task = Activity.objects.create(
            activity_type='task', title='Еженедельный обзвон', status='planned',
            due_date=due, recurrence_rule='FREQ=WEEKLY', responsible=self.owner, created_by=self.owner,
        )
        resp = self._patch_status_done(task.id)
        self.assertEqual(resp.status_code, 200)
        spawned_id = resp.json()['spawned_id']
        self.assertIsNotNone(spawned_id)
        spawned = Activity.objects.get(id=spawned_id)
        self.assertEqual(spawned.status, 'planned')
        self.assertEqual(spawned.recurrence_rule, 'FREQ=WEEKLY')
        self.assertEqual((spawned.due_date - due).days, 7)

    def test_completing_non_recurring_task_no_spawn(self):
        task = Activity.objects.create(
            activity_type='task', title='Разовая', status='planned',
            due_date=timezone.now(), responsible=self.owner, created_by=self.owner,
        )
        resp = self._patch_status_done(task.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['spawned_id'])
        self.assertEqual(Activity.objects.filter(activity_type='task').count(), 1)

    def test_calendar_endpoint_returns_tasks_in_range(self):
        today = timezone.now()
        Activity.objects.create(
            activity_type='task', title='В диапазоне', status='planned',
            due_date=today, responsible=self.owner, created_by=self.owner,
        )
        Activity.objects.create(
            activity_type='task', title='Вне диапазона', status='planned',
            due_date=today + timedelta(days=40), responsible=self.owner, created_by=self.owner,
        )
        d0 = (today - timedelta(days=1)).date().isoformat()
        d1 = (today + timedelta(days=1)).date().isoformat()
        resp = self.client.get(
            f'/api/crm/activities/calendar/?date_from={d0}&date_to={d1}',
            **self.auth_headers(self.owner),
        )
        self.assertEqual(resp.status_code, 200)
        titles = [a['title'] for a in resp.json()]
        self.assertIn('В диапазоне', titles)
        self.assertNotIn('Вне диапазона', titles)


class TaskReminderTaskTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.manager = self.create_user(role='manager', email='rem_mgr@example.com', username='rem_mgr')

    def test_reminder_sent_once_and_idempotent(self):
        from apps.crm.tasks import send_task_reminders

        Activity.objects.create(
            activity_type='task', title='Позвонить клиенту', status='planned',
            due_date=timezone.now() + timedelta(hours=2),
            remind_at=timezone.now() - timedelta(minutes=1),
            responsible=self.manager, created_by=self.manager,
        )
        result = send_task_reminders()
        self.assertEqual(result['sent'], 1)

        notes = Notification.objects.filter(user=self.manager, event='task_reminder')
        self.assertEqual(notes.count(), 1)

        task = Activity.objects.get(title='Позвонить клиенту')
        self.assertIsNotNone(task.reminder_sent_at)

        # Повторный прогон не дублирует напоминание (идемпотентность).
        result2 = send_task_reminders()
        self.assertEqual(result2['sent'], 0)
        self.assertEqual(Notification.objects.filter(user=self.manager, event='task_reminder').count(), 1)

    def test_future_reminder_not_sent_yet(self):
        from apps.crm.tasks import send_task_reminders

        Activity.objects.create(
            activity_type='task', title='Будущее', status='planned',
            due_date=timezone.now() + timedelta(days=2),
            remind_at=timezone.now() + timedelta(hours=1),
            responsible=self.manager, created_by=self.manager,
        )
        result = send_task_reminders()
        self.assertEqual(result['sent'], 0)
