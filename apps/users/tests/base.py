from __future__ import annotations

import uuid

from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.utils import schema_context, tenant_context
from ninja_jwt.tokens import RefreshToken

from apps.billing.models import Feature, Plan
from apps.users.models import Membership, User


ALL_FEATURE_CODES = [
    'distribution',
    'contracts',
    'contract_signing',
    'crm_bitrix24',
    'crm_amocrm',
    'analytics',
    'export_pdf',
    'export_excel',
    'custom_contract_templates',
    'api_access',
    'messenger_channels',
    'telephony',
    'crm_builtin',
]


class TenantAPITestCase(FastTenantTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return 'qa_test'

    @classmethod
    def get_test_tenant_domain(cls):
        return 'qa.localhost'

    @classmethod
    def setup_tenant(cls, tenant):
        plan = cls._ensure_crm_plan()
        tenant.name = 'QA Tenant'
        tenant.slug = 'qa'
        tenant.plan = plan
        tenant.crm_mode = 'builtin'
        tenant.is_active = True
        tenant.is_paid = True
        tenant.timezone = 'Europe/Moscow'
        tenant.language = 'ru'

    @classmethod
    def setup_domain(cls, domain):
        domain.is_primary = True

    @classmethod
    def use_existing_tenant(cls):
        plan = cls._ensure_crm_plan()
        with schema_context('public'):
            cls.tenant.plan = plan
            cls.tenant.slug = 'qa'
            cls.tenant.name = 'QA Tenant'
            cls.tenant.crm_mode = 'builtin'
            cls.tenant.is_active = True
            cls.tenant.save(
                update_fields=[
                    'plan',
                    'slug',
                    'name',
                    'crm_mode',
                    'is_active',
                ]
            )

    @classmethod
    def _ensure_crm_plan(cls):
        with schema_context('public'):
            plan = Plan.objects.filter(slug='crm').first()
            if plan:
                return plan
            plan = Plan.objects.create(
                name='CRM',
                slug='crm',
                max_managers=None,
                max_contracts_per_month=None,
                max_crm_connections=3,
                max_pipelines=None,
                price_monthly='0.00',
                is_active=True,
                sort_order=1,
            )
            feature_ids = []
            for code in ALL_FEATURE_CODES:
                feature, _ = Feature.objects.get_or_create(
                    code=code,
                    defaults={'name': code, 'description': ''},
                )
                feature_ids.append(feature.id)
            plan.features.set(feature_ids)
            return plan

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def _fixture_teardown(self):
        # FastTenantTestCase flushes data between tests; pin flush to tenant schema.
        connection.set_tenant(self.tenant)
        super()._fixture_teardown()

    def create_user(self, role: str = 'owner', email: str | None = None, username: str | None = None):
        email = email or f'{role}_{uuid.uuid4().hex[:8]}@example.com'
        username = username or email.split('@')[0]
        with schema_context('public'):
            user = User.objects.create_user(email=email, username=username, password='pass12345')
            Membership.objects.create(
                user=user,
                tenant_id=self.tenant.id,
                role=role,
                is_active=True,
                joined_at=timezone.now(),
            )
        return user

    def auth_headers(self, user, host: str = 'localhost', with_tenant_slug: bool = True):
        token = str(RefreshToken.for_user(user).access_token)
        headers = {
            'HTTP_AUTHORIZATION': f'Bearer {token}',
            'HTTP_HOST': host,
        }
        if with_tenant_slug:
            headers['HTTP_X_TENANT_SLUG'] = self.tenant.slug
        return headers

    def create_manager_profile(self, name: str = 'Manager', user=None, crm_user_id: str = '100'):
        from apps.integrations.models import ManagerProfile

        user = user or self.create_user(role='manager')
        with tenant_context(self.tenant):
            return ManagerProfile.objects.create(
                user=user,
                crm_user_id=str(crm_user_id),
                crm_user_name=name,
                max_active_deals=10,
                schedule={},
                is_active=True,
            )
