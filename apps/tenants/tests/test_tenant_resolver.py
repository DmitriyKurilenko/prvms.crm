from __future__ import annotations

from django.conf import settings
from django.test import RequestFactory
from django_tenants.utils import schema_context
from ninja.errors import HttpError

from apps.core.tenant import get_request_tenant
from apps.tenants.models import Domain, Tenant
from apps.users.tests.base import TenantAPITestCase


class TenantResolverTest(TenantAPITestCase):
    def test_root_endpoint_renders_landing_page(self):
        response = self.client.get('/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
        content = response.content.decode()
        # Проверяем по устойчивому бренд-маркеру, а не по маркетинговой копии,
        # которая меняется при редизайне лендинга.
        self.assertIn('ГусьБерри', content)
        self.assertIn('<html lang="ru"', content)

    def test_login_and_register_shortcuts_redirect_to_frontend(self):
        login_response = self.client.get('/login', HTTP_HOST='localhost')
        register_response = self.client.get('/register', HTTP_HOST='localhost')
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(register_response.status_code, 302)
        self.assertEqual(login_response['Location'], f"{settings.FRONTEND_APP_URL.rstrip('/')}/login")
        self.assertEqual(register_response['Location'], f"{settings.FRONTEND_APP_URL.rstrip('/')}/register")

    def test_host_based_resolution_for_tenant_domain(self):
        request = RequestFactory().get('/api/tenant/', HTTP_HOST=self.get_test_tenant_domain())
        tenant = get_request_tenant(request, required=True)
        self.assertEqual(tenant.id, self.tenant.id)

    def test_me_endpoint_on_localhost_with_tenant_header(self):
        owner = self.create_user(role='owner', email='resolver_owner@example.com', username='resolver_owner')
        headers = self.auth_headers(owner, host='localhost', with_tenant_slug=True)
        response = self.client.get('/api/auth/me', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tenant_slug'], self.tenant.slug)

    def test_raise_when_multiple_tenants_and_no_hint(self):
        second_tenant = None
        with schema_context('public'):
            second_tenant = Tenant.objects.create(
                schema_name='qa_second',
                slug='qa-second',
                name='QA Second',
                plan=self.tenant.plan,
                crm_mode='builtin',
                is_active=True,
            )
            Domain.objects.create(
                tenant=second_tenant,
                domain='qa-second.localhost',
                is_primary=True,
            )

        try:
            request = RequestFactory().get('/api/tenant/', HTTP_HOST='localhost')
            with self.assertRaises(HttpError):
                get_request_tenant(request, required=True)
        finally:
            with schema_context('public'):
                if second_tenant is not None:
                    second_tenant.delete(force_drop=True)
