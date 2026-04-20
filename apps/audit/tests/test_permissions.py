from __future__ import annotations

from apps.audit.models import AuditEvent
from apps.users.tests.base import TenantAPITestCase


class AuditPermissionsTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='audit_owner@example.com', username='audit_owner')
        self.manager = self.create_user(role='manager', email='audit_manager@example.com', username='audit_manager')
        AuditEvent.objects.create(
            user=self.owner,
            action='create',
            model_name='Deal',
            object_id='1',
            object_repr='Deal #1',
            changes={'status': {'before': None, 'after': 'created'}},
            ip_address='127.0.0.1',
            user_agent='test',
        )
        AuditEvent.objects.create(
            user=self.manager,
            action='update',
            model_name='Contact',
            object_id='2',
            object_repr='Contact #2',
            changes={'name': {'before': 'Old', 'after': 'New'}},
            ip_address='127.0.0.2',
            user_agent='test',
        )

    def test_owner_can_read_audit_events(self):
        response = self.client.get('/api/audit/events/', **self.auth_headers(self.owner, host='localhost'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total', data)
        self.assertIn('items', data)
        self.assertEqual(data['total'], 2)
        self.assertEqual(len(data['items']), 2)

    def test_manager_cannot_read_audit_events(self):
        response = self.client.get('/api/audit/events/', **self.auth_headers(self.manager, host='localhost'))
        self.assertEqual(response.status_code, 403)

    def test_filter_by_action(self):
        response = self.client.get(
            '/api/audit/events/?action=create',
            **self.auth_headers(self.owner, host='localhost'),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['items'][0]['action'], 'create')

    def test_filter_by_user_id(self):
        response = self.client.get(
            f'/api/audit/events/?user_id={self.manager.id}',
            **self.auth_headers(self.owner, host='localhost'),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['items'][0]['user_email'], self.manager.email)

    def test_filter_by_date_range(self):
        response = self.client.get(
            '/api/audit/events/?date_from=2020-01-01&date_to=2099-12-31',
            **self.auth_headers(self.owner, host='localhost'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 2)

    def test_user_email_in_response(self):
        response = self.client.get(
            f'/api/audit/events/?user_id={self.owner.id}',
            **self.auth_headers(self.owner, host='localhost'),
        )
        data = response.json()
        self.assertEqual(data['items'][0]['user_email'], self.owner.email)

    def test_export_csv_owner(self):
        response = self.client.get(
            '/api/audit/events/export/',
            **self.auth_headers(self.owner, host='localhost'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('user_email', content)
        self.assertIn('changes', content)

    def test_export_csv_manager_forbidden(self):
        response = self.client.get(
            '/api/audit/events/export/',
            **self.auth_headers(self.manager, host='localhost'),
        )
        self.assertEqual(response.status_code, 403)
