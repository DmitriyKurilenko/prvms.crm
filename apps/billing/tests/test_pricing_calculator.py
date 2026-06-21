from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.billing.models import Plan, PricingQuote, TelephonyQuoteRequest
from apps.tenants.models import Tenant


class PricingQuoteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_quote_basic(self):
        payload = {
            'users': 3,
            'messengers': ['telegram', 'vk'],
            'inbound_channels': ['site'],
            'documents': 100,
            'signatures': 50,
        }
        resp = self.client.post(
            '/api/public/pricing/quote/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # 3*1000 + 2*1000 + 1*1000 + 1*200 + 1*500 = 3000+2000+1000+200+500 = 6700
        self.assertEqual(data['monthly_total'], 6700)
        self.assertEqual(data['telephony_requires_quote'], False)
        self.assertTrue(data['quote_id'])
        self.assertEqual(len(data['breakdown']), 5)
        self.assertTrue(PricingQuote.objects.filter(id=data['quote_id']).exists())

    def test_quote_zero_messengers(self):
        payload = {
            'users': 1,
            'messengers': [],
            'inbound_channels': [],
            'documents': 0,
            'signatures': 0,
        }
        resp = self.client.post(
            '/api/public/pricing/quote/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['monthly_total'], 1000)

    def test_quote_telephony(self):
        payload = {
            'users': 1,
            'messengers': [],
            'inbound_channels': [],
            'documents': 0,
            'signatures': 0,
            'telephony': {'requested': True},
        }
        resp = self.client.post(
            '/api/public/pricing/quote/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['monthly_total'], 1000)
        self.assertTrue(data['telephony_requires_quote'])
        breakdown_labels = [b['label'] for b in data['breakdown']]
        self.assertIn('Телефония', breakdown_labels)

    def test_quote_documents_boundary(self):
        payload = {
            'users': 1,
            'messengers': [],
            'inbound_channels': [],
            'documents': 1000,
            'signatures': 0,
        }
        resp = self.client.post(
            '/api/public/pricing/quote/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # ceil(1000/100)=10 blocks -> 10*200=2000
        self.assertEqual(data['monthly_total'], 3000)

    def test_quote_expires_in_24h(self):
        payload = {'users': 1, 'messengers': [], 'inbound_channels': [], 'documents': 0, 'signatures': 0}
        resp = self.client.post(
            '/api/public/pricing/quote/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        quote_id = resp.json()['quote_id']
        quote = PricingQuote.objects.get(id=quote_id)
        self.assertTrue(quote.expires_at > timezone.now() + timedelta(hours=23))
        self.assertTrue(quote.expires_at <= timezone.now() + timedelta(hours=25))


class TelephonyRequestViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_telephony_request_success(self):
        payload = {
            'name': 'Иван',
            'email': 'ivan@example.com',
            'phone': '+79991234567',
            'configuration': {'lines': 3, 'minutes': 5000},
        }
        resp = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'ok')
        self.assertEqual(TelephonyQuoteRequest.objects.count(), 1)

    def test_telephony_request_honeypot(self):
        payload = {
            'name': 'Иван',
            'email': 'ivan@example.com',
            'website': 'spambot',
        }
        resp = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_telephony_request_rate_limit(self):
        payload = {
            'name': 'Иван',
            'email': 'ivan@example.com',
        }
        # first request ok
        resp1 = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp1.status_code, 200)
        # second request within 60s -> 429
        resp2 = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 429)

    def test_telephony_request_missing_contact(self):
        payload = {'name': 'Иван'}
        resp = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(SUPPORT_EMAIL='support@prvms.ru')
    @patch('apps.billing.public_views.send_email_async.delay')
    def test_contact_form_queues_email(self, mock_delay):
        payload = {
            'name': 'Пётр',
            'phone': '+79990001122',
            'email': 'petr@example.com',
            'configuration': {'message': 'Хочу навести порядок в заявках', 'source': 'landing-contact'},
        }
        resp = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TelephonyQuoteRequest.objects.count(), 1)
        mock_delay.assert_called_once()
        subject, body, from_email, recipients = mock_delay.call_args.args
        self.assertIn('Пётр', subject)
        self.assertEqual(recipients, ['support@prvms.ru'])
        self.assertIn('+79990001122', body)
        self.assertIn('Хочу навести порядок в заявках', body)

    @override_settings(SUPPORT_EMAIL='', DEFAULT_FROM_EMAIL='')
    @patch('apps.billing.public_views.send_email_async.delay')
    def test_contact_form_no_recipient_skips_email(self, mock_delay):
        payload = {
            'name': 'Анна',
            'phone': '+79993334455',
            'configuration': {'message': 'тест', 'source': 'landing-contact'},
        }
        resp = self.client.post(
            '/api/public/pricing/telephony-request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TelephonyQuoteRequest.objects.count(), 1)
        mock_delay.assert_not_called()


class QuoteRegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()

    def test_register_with_free_custom_quote(self):
        # Ensure free-custom plan exists
        plan, _ = Plan.objects.update_or_create(
            slug='free-custom',
            defaults={'name': 'СВОБОДНЫЙ', 'kind': 'custom', 'price_monthly': 0, 'is_active': True},
        )

        quote = PricingQuote.objects.create(
            expires_at=timezone.now() + timedelta(hours=24),
            config={'users': 3, 'messengers': ['telegram', 'vk'], 'inbound_channels': ['site'], 'documents': 100, 'signatures': 50},
            monthly_total=4500,
        )

        org_slug = 'test-quote-reg'
        resp = self.client.post(
            '/api/auth/register',
            data=json.dumps({
                'email': 'quoteuser@example.com',
                'password': 'TestPass123',
                'username': 'quoteuser',
                'org_name': 'Quote Org',
                'org_slug': org_slug,
                'plan_slug': 'free-custom',
                'quote_id': str(quote.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        with schema_context('public'):
            tenant = Tenant.objects.get(slug=org_slug)
            self.assertEqual(tenant.plan.slug, 'free-custom')
            self.assertEqual(tenant.custom_limits.get('max_managers'), 3)
            self.assertEqual(tenant.custom_limits.get('monthly_total'), 4500)
            self.assertEqual(tenant.custom_limits.get('quote_id'), str(quote.id))
            tenant.delete(force_drop=True)

    def test_register_with_expired_quote_fails(self):
        Plan.objects.update_or_create(
            slug='free-custom',
            defaults={'name': 'СВОБОДНЫЙ', 'kind': 'custom', 'price_monthly': 0, 'is_active': True},
        )
        quote = PricingQuote.objects.create(
            expires_at=timezone.now() - timedelta(hours=1),
            config={'users': 1},
            monthly_total=1000,
        )
        resp = self.client.post(
            '/api/auth/register',
            data=json.dumps({
                'email': 'expired@example.com',
                'password': 'TestPass123',
                'username': 'expireduser',
                'org_name': 'Expired Org',
                'org_slug': 'expired-quote',
                'plan_slug': 'free-custom',
                'quote_id': str(quote.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Quote expired', resp.json()['detail'])
