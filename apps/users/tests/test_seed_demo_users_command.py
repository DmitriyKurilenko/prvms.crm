from __future__ import annotations

from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context

from apps.crm.models import Pipeline
from apps.tenants.models import Tenant
from apps.users.models import Membership, User

from .base import TenantAPITestCase


class SeedDemoUsersCommandTest(TenantAPITestCase):
    def test_seed_demo_users_creates_tenants_users_and_memberships(self):
        call_command('seed_demo_users', '--count', '2', '--password', 'SeedPass123', '--force')

        with schema_context('public'):
            self.assertEqual(Tenant.objects.filter(slug__startswith='company-').count(), 2)

            expected_users = [
                'test1@test.ru',
                'test2@test.ru',
                'test3@test.ru',
                'test4@test.ru',
                'test5@test.ru',
                'test6@test.ru',
                'admin@test.ru',
            ]
            for email in expected_users:
                user = User.objects.get(email=email)
                self.assertTrue(user.check_password('SeedPass123'))

            admin = User.objects.get(email='admin@test.ru')
            self.assertTrue(admin.is_staff)
            self.assertTrue(admin.is_superuser)

            t1 = Tenant.objects.get(slug='company-1')
            t2 = Tenant.objects.get(slug='company-2')

            # Memberships
            for tenant, offset in ((t1, 0), (t2, 3)):
                for role_idx, role in enumerate(('owner', 'admin', 'manager')):
                    email = f'test{offset + role_idx + 1}@test.ru'
                    m = Membership.objects.get(user__email=email, tenant=tenant)
                    self.assertEqual(m.role, role)
                    self.assertTrue(m.is_active)
                    self.assertIsNotNone(m.joined_at)

            admin_membership = Membership.objects.get(user=admin, tenant=t1)
            self.assertEqual(admin_membership.role, 'admin')

            # Trial not expired
            for t in (t1, t2):
                self.assertIsNotNone(t.trial_expires_at)
                self.assertGreater(t.trial_expires_at, timezone.now())
                self.assertFalse(t.trial_expired)

        # Pipelines provisioned
        with tenant_context(t1):
            self.assertTrue(Pipeline.objects.filter(is_default=True).exists())
        with tenant_context(t2):
            self.assertTrue(Pipeline.objects.filter(is_default=True).exists())

    def tearDown(self):
        # Manually drop schemas and clean up shared rows created by the command.
        with connection.cursor() as cursor:
            for i in range(1, 3):
                cursor.execute(f'DROP SCHEMA IF EXISTS "company-{i}" CASCADE')

        with schema_context('public'):
            # Raw SQL to avoid ORM cascade into tenant-scoped tables (e.g. team_manager).
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM users_membership WHERE tenant_id IN (SELECT id FROM tenants_tenant WHERE slug LIKE 'company-%%')"
                )
                cursor.execute(
                    "DELETE FROM tenants_domain WHERE tenant_id IN (SELECT id FROM tenants_tenant WHERE slug LIKE 'company-%%')"
                )
                cursor.execute(
                    "DELETE FROM tenants_tenant WHERE slug LIKE 'company-%%'"
                )
                cursor.execute(
                    "DELETE FROM users_user WHERE email LIKE 'test%%@test.ru' OR email = 'admin@test.ru'"
                )

        super().tearDown()
