from __future__ import annotations

import json
from unittest.mock import patch
from xml.etree import ElementTree as ET

from django.conf import settings

from apps.telephony.models import PhoneExtension, SIPTrunk
from apps.users.tests.base import TenantAPITestCase

_FS_TOKEN = settings.FREESWITCH_ESL_PASSWORD
_AUTH = {'HTTP_X_FREESWITCH_TOKEN': _FS_TOKEN}


class TelephonyPublicEndpointsTest(TenantAPITestCase):

    # ------------------------------------------------------------------ #
    # dialplan
    # ------------------------------------------------------------------ #

    def test_dialplan_requires_ip_authorization(self):
        """Requests from non-allowed IPs must be rejected (403)."""
        response = self.client.post(
            '/telephony/dialplan/',
            data=json.dumps({'tenant_slug': self.tenant.slug, 'called_number': '101'}),
            content_type='application/json',
            HTTP_HOST='localhost',
            REMOTE_ADDR='1.2.3.4',
        )
        self.assertEqual(response.status_code, 403)

    def test_dialplan_returns_xml_content_type(self):
        """A valid request must return text/xml."""
        manager = self.create_manager_profile(name='Phone Manager', crm_user_id='201')
        PhoneExtension.objects.create(manager=manager, extension='101', sip_password='secret', is_active=True)
        response = self.client.post(
            '/telephony/dialplan/',
            data=json.dumps({'tenant_slug': self.tenant.slug, 'called_number': '101', 'caller_number': '+70000000000'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response['Content-Type'])

    def test_dialplan_routes_to_manager_extension(self):
        """dialplan must produce a valid FS XML bridge action for a known extension."""
        manager = self.create_manager_profile(name='Phone Manager', crm_user_id='201')
        PhoneExtension.objects.create(manager=manager, extension='101', sip_password='secret', is_active=True)
        response = self.client.post(
            '/telephony/dialplan/',
            data=json.dumps({'tenant_slug': self.tenant.slug, 'called_number': '101', 'caller_number': '+70000000000'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content.decode())
        self.assertEqual(root.get('type'), 'freeswitch/xml')
        self.assertEqual(root.find('section').get('name'), 'dialplan')
        actions = root.findall('.//action')
        bridge = [a for a in actions if a.get('application') == 'bridge']
        self.assertTrue(any('user/101' in (a.get('data') or '') for a in bridge))

    def test_dialplan_hangup_when_no_route(self):
        """dialplan must return a hangup action when nothing matches."""
        response = self.client.post(
            '/telephony/dialplan/',
            data=json.dumps({'tenant_slug': self.tenant.slug, 'called_number': '999', 'caller_number': '+70000000001'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('hangup', response.content.decode())

    def test_dialplan_normalises_freeswitch_field_names(self):
        """FS sends Caller-Destination-Number; service must normalise it."""
        manager = self.create_manager_profile(name='FS Field Manager', crm_user_id='202')
        PhoneExtension.objects.create(manager=manager, extension='102', sip_password='s2', is_active=True)
        response = self.client.post(
            '/telephony/dialplan/',
            data={
                'tenant_slug': self.tenant.slug,
                'Caller-Destination-Number': '102',
                'Caller-Caller-ID-Number': '+70000000002',
            },
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        actions = ET.fromstring(response.content.decode()).findall('.//action')
        bridge = [a for a in actions if a.get('application') == 'bridge']
        self.assertTrue(any('user/102' in (a.get('data') or '') for a in bridge))

    # ------------------------------------------------------------------ #
    # directory
    # ------------------------------------------------------------------ #

    def test_directory_returns_extension_credentials(self):
        """directory must return a valid user XML with password for a known extension."""
        manager = self.create_manager_profile(name='Dir Manager', crm_user_id='301')
        PhoneExtension.objects.create(manager=manager, extension='103', sip_password='dirpass', is_active=True)
        response = self.client.post(
            '/telephony/directory/',
            data={'tenant_slug': self.tenant.slug, 'user': '103', 'domain': 'freeswitch.local'},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content.decode())
        self.assertEqual(root.get('type'), 'freeswitch/xml')
        self.assertEqual(root.find('section').get('name'), 'directory')
        user_el = root.find('.//user')
        self.assertIsNotNone(user_el)
        self.assertEqual(user_el.get('id'), '103')
        passwords = [p for p in root.findall('.//param') if p.get('name') == 'password']
        self.assertTrue(any(p.get('value') == 'dirpass' for p in passwords))

    def test_directory_not_found_for_unknown_extension(self):
        """directory must return a not-found result XML for unknown extension."""
        response = self.client.post(
            '/telephony/directory/',
            data={'tenant_slug': self.tenant.slug, 'user': '999', 'domain': 'freeswitch.local'},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('not found', response.content.decode())

    def test_directory_includes_tenant_slug_variable(self):
        """directory XML must embed tenant_slug so FS propagates it as a channel var."""
        manager = self.create_manager_profile(name='TSlug Manager', crm_user_id='302')
        PhoneExtension.objects.create(manager=manager, extension='104', sip_password='p', is_active=True)
        response = self.client.post(
            '/telephony/directory/',
            data={'tenant_slug': self.tenant.slug, 'user': '104', 'domain': 'freeswitch.local'},
            HTTP_HOST='localhost',
        )
        body = response.content.decode()
        self.assertIn(self.tenant.slug, body)

    # ------------------------------------------------------------------ #
    # events
    # ------------------------------------------------------------------ #

    @patch('apps.telephony.public_views.process_freeswitch_cdr.delay')
    def test_events_endpoint_queues_cdr_processing(self, mock_delay):
        payload = {
            'tenant_slug': self.tenant.slug,
            'uuid': 'uuid-1',
            'caller_number': '+79990000000',
            'called_number': '101',
        }
        response = self.client.post(
            '/telephony/events/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_HOST='localhost',
            **_AUTH,
        )
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once_with(self.tenant.id, payload)

    def test_events_rejects_missing_token(self):
        """events endpoint must require the X-FreeSWITCH-Token header."""
        response = self.client.post(
            '/telephony/events/',
            data=json.dumps({'tenant_slug': self.tenant.slug, 'uuid': 'x'}),
            content_type='application/json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------ #
    # configuration
    # ------------------------------------------------------------------ #

    def test_configuration_requires_ip_auth(self):
        """Requests from non-allowed IPs must be rejected (403)."""
        response = self.client.post(
            '/telephony/configuration/',
            HTTP_HOST='localhost',
            REMOTE_ADDR='1.2.3.4',
        )
        self.assertEqual(response.status_code, 403)

    def test_configuration_returns_xml_content_type(self):
        """configuration endpoint must return text/xml."""
        response = self.client.post('/telephony/configuration/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response['Content-Type'])

    def test_configuration_includes_active_trunks(self):
        """Active trunk must appear as a gateway in the configuration XML."""
        SIPTrunk.objects.create(
            name='test-trunk',
            trunk_type='custom_sip',
            credentials={'username': 'user1', 'password': 'pass1', 'proxy': 'sip.example.com'},
            is_active=True,
        )
        response = self.client.post('/telephony/configuration/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('test-trunk', body)
        self.assertIn('sip.example.com', body)
        self.assertIn(self.tenant.slug, body)

    def test_configuration_excludes_inactive_trunks(self):
        """Inactive trunk must NOT appear in the configuration XML."""
        SIPTrunk.objects.create(
            name='inactive-trunk',
            trunk_type='custom_sip',
            credentials={'username': 'u', 'password': 'p', 'proxy': 'sip.inactive.com'},
            is_active=False,
        )
        response = self.client.post('/telephony/configuration/', HTTP_HOST='localhost')
        body = response.content.decode()
        self.assertNotIn('inactive-trunk', body)

    # ------------------------------------------------------------------ #
    # SIP domain isolation (Phase 8)
    # ------------------------------------------------------------------ #

    def test_directory_resolves_tenant_by_sip_domain(self):
        """directory must resolve tenant when FS sends domain_name = tenant.sip_domain."""
        from apps.telephony.models import PhoneExtension
        # Ensure tenant has a sip_domain set
        sip_domain = self.tenant.sip_domain or f'{self.tenant.slug}.sip.localhost'
        self.tenant.sip_domain = sip_domain
        self.tenant.save(update_fields=['sip_domain'])

        manager = self.create_manager_profile(name='SIP Domain Mgr', crm_user_id='801')
        PhoneExtension.objects.create(manager=manager, extension='150', sip_password='sipdpass', is_active=True)

        response = self.client.post(
            '/telephony/directory/',
            data={'domain_name': sip_domain, 'user': '150', 'domain': sip_domain},
            HTTP_HOST='localhost',
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('150', body)
        self.assertNotIn('not found', body)
