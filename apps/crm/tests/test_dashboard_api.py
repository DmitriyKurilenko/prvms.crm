from __future__ import annotations

from unittest.mock import patch

from django.utils import timezone

from apps.crm.models import Deal, Pipeline, Stage
from apps.distribution.models import DistributionLog
from apps.documents.models import Document, DocumentTemplate
from apps.telephony.models import CallRecord
from apps.users.tests.base import TenantAPITestCase


class DashboardAPITest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='dashboard_owner@example.com', username='dashboard_owner')
        self.manager_user = self.create_user(role='manager', email='dash_manager@example.com', username='dash_manager')
        self.manager_profile = self.create_manager_profile(name='Dash Manager', user=self.manager_user, crm_user_id='401')

        self.pipeline = Pipeline.objects.create(name='Dashboard Pipeline', is_default=True, sort_order=0, is_active=True)
        self.stage_open = Stage.objects.create(
            pipeline=self.pipeline,
            name='Open',
            stage_type='open',
            sort_order=0,
            auto_action={},
        )
        self.stage_won = Stage.objects.create(
            pipeline=self.pipeline,
            name='Won',
            stage_type='won',
            sort_order=1,
            auto_action={},
        )

        Deal.objects.create(
            name='Open deal',
            pipeline=self.pipeline,
            stage=self.stage_open,
            responsible=self.manager_user,
            source='manual',
        )
        Deal.objects.create(
            name='Won deal',
            pipeline=self.pipeline,
            stage=self.stage_won,
            responsible=self.manager_user,
            source='manual',
        )

        template = DocumentTemplate.objects.create(
            name='Dashboard Document',
            version=1,
            html_body='<h1>x</h1>',
            variable_schema=[],
            is_active=True,
        )
        Document.objects.create(
            template=template,
            template_version=1,
            crm_entity_type='manual',
            crm_entity_id='1',
            filled_data={},
            html_snapshot='<h1>x</h1>',
            status='signed',
            signed_at=timezone.now(),
            created_by=self.owner,
        )

        DistributionLog.objects.create(
            rule=None,
            crm_connection=None,
            crm_entity_type='lead',
            crm_entity_id='lead-1',
            assigned_to=self.manager_profile,
            source='manual',
            strategy_used='min_load',
            reason='test',
        )
        CallRecord.objects.create(
            call_sid='dash-call-1',
            direction='inbound',
            caller_number='+79990000001',
            called_number='101',
            result='missed',
            duration=0,
            wait_time=0,
            manager=self.manager_profile,
            started_at=timezone.now(),
        )

    def test_dashboard_stats_aggregates_entities(self):
        headers = self.auth_headers(self.owner, host='localhost')
        response = self.client.get('/api/dashboard/stats/', **headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['deals_open'], 1)
        self.assertEqual(payload['deals_won'], 1)
        self.assertEqual(payload['documents_total'], 1)
        self.assertEqual(payload['documents_signed'], 1)
        self.assertEqual(payload['distribution_total'], 1)
        self.assertEqual(payload['calls_total'], 1)
        self.assertEqual(payload['calls_missed'], 1)

    def test_managers_online_returns_zero_when_no_presence(self):
        headers = self.auth_headers(self.owner, host='localhost')
        with patch('apps.crm.dashboard_api.list_online_user_ids', return_value=set()):
            response = self.client.get('/api/dashboard/managers-online/', **headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['online'], 0)
        self.assertGreaterEqual(payload['total'], 2)
        self.assertEqual(payload['user_ids'], [])

    def test_managers_online_counts_only_eligible_members(self):
        viewer = self.create_user(role='viewer', email='dash_viewer@example.com', username='dash_viewer')
        online_ids = {self.owner.id, self.manager_user.id, viewer.id, 999999}
        headers = self.auth_headers(self.owner, host='localhost')
        with patch('apps.crm.dashboard_api.list_online_user_ids', return_value=online_ids):
            response = self.client.get('/api/dashboard/managers-online/', **headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['online'], 2)
        self.assertCountEqual(payload['user_ids'], [self.owner.id, self.manager_user.id])
        self.assertNotIn(viewer.id, payload['user_ids'])

    def test_managers_online_requires_analytics_feature(self):
        from django_tenants.utils import schema_context

        from apps.billing.models import Feature

        plan = self.tenant.plan
        with schema_context('public'):
            analytics = Feature.objects.get(code='analytics')
            plan.features.remove(analytics)
        try:
            headers = self.auth_headers(self.owner, host='localhost')
            with patch('apps.crm.dashboard_api.list_online_user_ids', return_value=set()):
                response = self.client.get('/api/dashboard/managers-online/', **headers)
            self.assertEqual(response.status_code, 403)
        finally:
            with schema_context('public'):
                plan.features.add(Feature.objects.get(code='analytics'))
