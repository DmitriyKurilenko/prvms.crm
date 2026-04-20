from __future__ import annotations

import json

from .base import TenantAPITestCase


class RolePermissionsApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='perm_owner@example.com', username='perm_owner')
        self.manager = self.create_user(role='manager', email='perm_manager@example.com', username='perm_manager')

    def test_owner_can_list_and_update_role_permissions(self):
        owner_headers = self.auth_headers(self.owner, host='localhost')

        list_response = self.client.get('/api/users/role-permissions/', **owner_headers)
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertIn('roles', payload)
        self.assertIn('manager', payload['roles'])
        self.assertIn('deals', payload['roles']['manager'])

        patch_response = self.client.patch(
            '/api/users/role-permissions/manager/deals/',
            data=json.dumps({'scope': 'own', 'can_delete': False}),
            content_type='application/json',
            **owner_headers,
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()['permission']['scope'], 'own')

        manager_headers = self.auth_headers(self.manager, host='localhost')
        me_response = self.client.get('/api/auth/me', **manager_headers)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()['crm_permissions']['deals']['scope'], 'own')

    def test_non_admin_cannot_update_permissions_matrix(self):
        manager_headers = self.auth_headers(self.manager, host='localhost')

        list_response = self.client.get('/api/users/role-permissions/', **manager_headers)
        self.assertEqual(list_response.status_code, 403)

        patch_response = self.client.patch(
            '/api/users/role-permissions/manager/contacts/',
            data=json.dumps({'can_delete': True}),
            content_type='application/json',
            **manager_headers,
        )
        self.assertEqual(patch_response.status_code, 403)
