from __future__ import annotations

import json

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.users.tests.base import TenantAPITestCase

PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    b'\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178\xe4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class TenantSettingsApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(role='owner', email='ts_owner@example.com', username='ts_owner')
        self.admin = self.create_user(role='admin', email='ts_admin@example.com', username='ts_admin')
        self.manager = self.create_user(role='manager', email='ts_manager@example.com', username='ts_manager')

    def _patch_settings(self, user, payload):
        headers = self.auth_headers(user, host='localhost')
        return self.client.patch(
            '/api/tenant/settings',
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    def test_patch_valid_settings(self):
        response = self._patch_settings(
            self.owner,
            {
                'name': 'New Co',
                'brand_color': '#112233',
                'timezone': 'Asia/Novosibirsk',
                'language': 'en',
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload['name'], 'New Co')
        self.assertEqual(payload['brand_color'], '#112233')
        self.assertEqual(payload['timezone'], 'Asia/Novosibirsk')
        self.assertEqual(payload['language'], 'en')

    def test_patch_invalid_brand_color(self):
        response = self._patch_settings(self.owner, {'brand_color': 'red'})
        self.assertEqual(response.status_code, 400)

    def test_patch_invalid_timezone(self):
        response = self._patch_settings(self.owner, {'timezone': 'Atlantis/Lost'})
        self.assertEqual(response.status_code, 400)

    def test_patch_invalid_language(self):
        response = self._patch_settings(self.owner, {'language': 'fr'})
        self.assertEqual(response.status_code, 400)

    def test_patch_denied_for_manager(self):
        response = self._patch_settings(self.manager, {'name': 'Hacked Co'})
        self.assertEqual(response.status_code, 403)

    def test_get_tenant_exposes_logo_url_field(self):
        headers = self.auth_headers(self.owner, host='localhost')
        response = self.client.get('/api/tenant/', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('logo_url', response.json())

    def test_upload_logo_and_read_back(self):
        headers = self.auth_headers(self.owner, host='localhost')
        upload = SimpleUploadedFile('logo.png', PNG_1x1, content_type='image/png')
        response = self.client.post('/api/tenant/logo', data={'file': upload}, **headers)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['logo_url'])

        response = self.client.get('/api/tenant/', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['logo_url'])

        response = self.client.delete('/api/tenant/logo', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['logo_url'])

    def test_upload_logo_rejects_admin(self):
        headers = self.auth_headers(self.admin, host='localhost')
        upload = SimpleUploadedFile('logo.png', PNG_1x1, content_type='image/png')
        response = self.client.post('/api/tenant/logo', data={'file': upload}, **headers)
        self.assertEqual(response.status_code, 403)

    def test_upload_logo_rejects_oversize(self):
        headers = self.auth_headers(self.owner, host='localhost')
        blob = b'\x00' * (3 * 1024 * 1024)
        upload = SimpleUploadedFile('big.png', blob, content_type='image/png')
        response = self.client.post('/api/tenant/logo', data={'file': upload}, **headers)
        self.assertEqual(response.status_code, 400)

    def test_upload_logo_rejects_bad_content_type(self):
        headers = self.auth_headers(self.owner, host='localhost')
        upload = SimpleUploadedFile('logo.exe', b'MZ', content_type='application/octet-stream')
        response = self.client.post('/api/tenant/logo', data={'file': upload}, **headers)
        self.assertEqual(response.status_code, 400)
