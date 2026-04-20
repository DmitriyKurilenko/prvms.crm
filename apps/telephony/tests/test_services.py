from __future__ import annotations

from xml.etree import ElementTree as ET

from apps.telephony.models import CallQueue, IVRMenu, PhoneExtension, SIPTrunk
from apps.users.tests.base import TenantAPITestCase


class IVRTTSTest(TenantAPITestCase):

    def _post_dialplan(self, payload):
        return self.client.post(
            '/telephony/dialplan/',
            data=__import__('json').dumps(payload),
            content_type='application/json',
            HTTP_HOST='localhost',
        )

    def test_ivr_uses_speak_when_tts_set(self):
        IVRMenu.objects.create(
            name='main-ivr',
            greeting_tts='Добро пожаловать, нажмите один',
            options=[],
            timeout=10,
            is_active=True,
        )
        response = self._post_dialplan({'tenant_slug': self.tenant.slug, 'called_number': '999'})
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('speak', body)
        self.assertIn('flite|kal', body)
        self.assertIn('Добро пожаловать', body)

    def test_ivr_uses_sleep_when_no_tts(self):
        IVRMenu.objects.create(
            name='silent-ivr',
            greeting_tts='',
            options=[],
            timeout=10,
            is_active=True,
        )
        response = self._post_dialplan({'tenant_slug': self.tenant.slug, 'called_number': '999'})
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('sleep', body)
        self.assertNotIn('speak', body)


class DIDRoutingTest(TenantAPITestCase):

    def _post_dialplan(self, payload):
        return self.client.post(
            '/telephony/dialplan/',
            data=__import__('json').dumps(payload),
            content_type='application/json',
            HTTP_HOST='localhost',
        )

    def test_did_routes_to_ivr(self):
        SIPTrunk.objects.create(
            name='did-trunk',
            trunk_type='custom_sip',
            credentials={'username': 'u', 'password': 'p', 'proxy': 'sip.example.com'},
            inbound_numbers=['+79991234567'],
            is_active=True,
        )
        IVRMenu.objects.create(
            name='did-ivr', greeting_tts='', options=[], timeout=10, is_active=True,
        )
        response = self._post_dialplan({
            'tenant_slug': self.tenant.slug,
            'called_number': '+79991234567',
            'caller_number': '+70000000000',
        })
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # DID hit → IVR, not hangup
        self.assertIn('ivr', body)
        self.assertNotIn('NO_ROUTE', body)

    def test_did_routes_to_queue_when_no_ivr(self):
        SIPTrunk.objects.create(
            name='did-trunk-q',
            trunk_type='custom_sip',
            credentials={'username': 'u', 'password': 'p', 'proxy': 'sip.example.com'},
            inbound_numbers=['+79997654321'],
            is_active=True,
        )
        CallQueue.objects.create(name='sales', strategy='ring_all', is_active=True)
        response = self._post_dialplan({
            'tenant_slug': self.tenant.slug,
            'called_number': '+79997654321',
            'caller_number': '+70000000001',
        })
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('callcenter', body)

    def test_unmatched_did_falls_through_to_extension(self):
        manager = self.create_manager_profile(name='DID Test Mgr', crm_user_id='501')
        PhoneExtension.objects.create(
            manager=manager, extension='200', sip_password='s', is_active=True,
        )
        # No trunk with this DID registered
        response = self._post_dialplan({
            'tenant_slug': self.tenant.slug,
            'called_number': '200',
            'caller_number': '+70000000002',
        })
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('user/200', body)
