from __future__ import annotations

import json

from apps.crm.models import Contact, Deal, Pipeline, Stage
from apps.users.tests.base import TenantAPITestCase


class CRMRolePermissionsApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='crm_perm_owner@example.com', username='crm_perm_owner')
        self.manager = self.create_user(role='manager', email='crm_perm_manager@example.com', username='crm_perm_manager')
        self.viewer = self.create_user(role='viewer', email='crm_perm_viewer@example.com', username='crm_perm_viewer')

        self.pipeline = Pipeline.objects.create(name='Sales', is_default=True, sort_order=0, is_active=True)
        self.stage = Stage.objects.create(
            pipeline=self.pipeline,
            name='New',
            stage_type='open',
            sort_order=0,
            auto_action={},
        )

        self.owner_deal = Deal.objects.create(
            name='Owner deal',
            pipeline=self.pipeline,
            stage=self.stage,
            responsible=self.owner,
            source='manual',
        )
        self.manager_deal = Deal.objects.create(
            name='Manager deal',
            pipeline=self.pipeline,
            stage=self.stage,
            responsible=self.manager,
            source='manual',
        )

    def _set_role_permission(self, role: str, entity: str, payload: dict):
        owner_headers = self.auth_headers(self.owner, host='localhost')
        response = self.client.patch(
            f'/api/users/role-permissions/{role}/{entity}/',
            data=json.dumps(payload),
            content_type='application/json',
            **owner_headers,
        )
        self.assertEqual(response.status_code, 200)

    def test_viewer_has_read_only_access_by_default(self):
        viewer_headers = self.auth_headers(self.viewer, host='localhost')

        list_response = self.client.get('/api/crm/deals/', **viewer_headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.json()), 2)

        create_response = self.client.post(
            '/api/crm/deals/',
            data=json.dumps(
                {
                    'name': 'Viewer cannot create',
                    'pipeline_id': self.pipeline.id,
                    'stage_id': self.stage.id,
                }
            ),
            content_type='application/json',
            **viewer_headers,
        )
        self.assertEqual(create_response.status_code, 403)

    def test_scope_own_limits_manager_deals_and_updates(self):
        self._set_role_permission('manager', 'deals', {'scope': 'own'})
        manager_headers = self.auth_headers(self.manager, host='localhost')

        list_response = self.client.get('/api/crm/deals/', **manager_headers)
        self.assertEqual(list_response.status_code, 200)
        deal_ids = {item['id'] for item in list_response.json()}
        self.assertIn(self.manager_deal.id, deal_ids)
        self.assertNotIn(self.owner_deal.id, deal_ids)

        patch_forbidden = self.client.patch(
            f'/api/crm/deals/{self.owner_deal.id}/',
            data=json.dumps({'name': 'Should fail'}),
            content_type='application/json',
            **manager_headers,
        )
        self.assertEqual(patch_forbidden.status_code, 403)

        patch_own = self.client.patch(
            f'/api/crm/deals/{self.manager_deal.id}/',
            data=json.dumps({'name': 'Updated by manager'}),
            content_type='application/json',
            **manager_headers,
        )
        self.assertEqual(patch_own.status_code, 200)

    def test_own_scope_create_sets_responsible_to_actor(self):
        self._set_role_permission('manager', 'contacts', {'scope': 'own'})
        manager_headers = self.auth_headers(self.manager, host='localhost')

        create_response = self.client.post(
            '/api/crm/contacts/',
            data=json.dumps({'first_name': 'Scoped contact'}),
            content_type='application/json',
            **manager_headers,
        )
        self.assertEqual(create_response.status_code, 200)
        contact_id = create_response.json()['id']

        contact = Contact.objects.get(id=contact_id)
        self.assertEqual(contact.responsible_id, self.manager.id)

        list_response = self.client.get('/api/crm/contacts/', **manager_headers)
        self.assertEqual(list_response.status_code, 200)
        returned_ids = {item['id'] for item in list_response.json()}
        self.assertIn(contact_id, returned_ids)
