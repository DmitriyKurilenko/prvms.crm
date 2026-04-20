from __future__ import annotations

from unittest.mock import Mock, patch

from apps.distribution.models import DistributionRule
from apps.distribution.services import assign_entity
from apps.users.tests.base import TenantAPITestCase


class DistributionAssignmentTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.manager1 = self.create_manager_profile(name='Manager 1', crm_user_id='501')
        self.manager2 = self.create_manager_profile(name='Manager 2', crm_user_id='502')
        self.fallback = self.create_manager_profile(name='Fallback', crm_user_id='599')

    @patch('apps.distribution.services.notify')
    @patch('apps.distribution.services.get_adapter_for_tenant')
    def test_assign_entity_uses_fallback_manager_when_no_candidates(self, mock_get_adapter, _mock_notify):
        rule = DistributionRule.objects.create(
            name='Fallback Rule',
            trigger='new_lead',
            strategy='manual_queue',
            strategy_config={},
            fallback_manager=self.fallback,
            is_active=True,
        )
        adapter = Mock()
        mock_get_adapter.return_value = adapter

        log = assign_entity(
            rule=rule,
            entity_type='lead',
            entity_id='lead-1',
            source='manual',
            payload={},
        )

        self.assertEqual(log.assigned_to_id, self.fallback.id)
        self.assertIn('fallback_manager', log.reason)
        adapter.set_responsible.assert_called_once_with('lead', 'lead-1', str(self.fallback.crm_user_id))

    @patch('apps.distribution.services.notify')
    @patch('apps.distribution.services.get_adapter_for_tenant')
    def test_round_robin_updates_strategy_cursor(self, mock_get_adapter, _mock_notify):
        rule = DistributionRule.objects.create(
            name='RR Rule',
            trigger='new_lead',
            strategy='round_robin',
            strategy_config={},
            is_active=True,
        )
        rule.managers.set([self.manager1, self.manager2])
        adapter = Mock()
        mock_get_adapter.return_value = adapter

        log1 = assign_entity(rule, 'lead', '1', 'manual', {})
        log2 = assign_entity(rule, 'lead', '2', 'manual', {})
        rule.refresh_from_db()

        self.assertNotEqual(log1.assigned_to_id, log2.assigned_to_id)
        self.assertIn('last_assigned_index', rule.strategy_config)
        self.assertEqual(adapter.set_responsible.call_count, 2)
