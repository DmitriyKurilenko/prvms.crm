from __future__ import annotations

from uuid import uuid4

from django.core.management import call_command
from django_tenants.utils import schema_context, tenant_context

from apps.billing.models import Plan
from apps.tenants.models import Domain, Tenant
from apps.users.models import Membership, User
from .base import TenantAPITestCase


class CreateTestUsersCommandTest(TenantAPITestCase):
    def test_command_does_not_reset_password_without_flag(self):
        call_command(
            'create_test_users',
            '--tenant-slug',
            self.tenant.slug,
            '--password',
            'InitialPass123',
        )
        call_command(
            'create_test_users',
            '--tenant-slug',
            self.tenant.slug,
            '--password',
            'UpdatedPass123',
        )

        with schema_context('public'):
            owner = User.objects.get(email=f'owner_{self.tenant.slug}@example.com')
            self.assertTrue(owner.check_password('InitialPass123'))
            self.assertFalse(owner.check_password('UpdatedPass123'))

    def test_command_without_args_reconciles_existing_bootstrap_tenant(self):
        with schema_context('public'):
            crm_plan = Plan.objects.get(slug='crm')
            broken_tenant = Tenant(
                name='Broken Basic Org',
                slug='org-basic',
                schema_name='org-basic',
                plan=crm_plan,
                crm_mode='amocrm',
                is_active=False,
            )
            broken_tenant.save()
            Domain.objects.create(tenant=broken_tenant, domain='legacy-basic.localhost', is_primary=True)

        call_command('create_test_users')

        with schema_context('public'):
            org_basic = Tenant.objects.get(slug='org-basic')
            self.assertEqual(org_basic.plan.slug, 'basic')
            self.assertEqual(org_basic.name, 'Demo Basic Org')
            self.assertEqual(org_basic.crm_mode, 'builtin')
            self.assertTrue(org_basic.is_active)

            default_domain = Domain.objects.get(tenant=org_basic, domain='org-basic.localhost')
            self.assertTrue(default_domain.is_primary)
            self.assertFalse(
                Domain.objects.get(tenant=org_basic, domain='legacy-basic.localhost').is_primary
            )

            # Keep fallback behaviour predictable for tests that rely on active tenant count.
            Tenant.objects.filter(slug__in=('org-simple', 'org-basic', 'org-crm')).update(is_active=False)

    def test_command_without_args_creates_bootstrap_seed(self):
        call_command('create_test_users')

        with schema_context('public'):
            expected = {
                'org-simple': 'simple',
                'org-basic': 'basic',
                'org-crm': 'crm',
            }
            for slug, plan_slug in expected.items():
                tenant = Tenant.objects.get(slug=slug)
                self.assertEqual(tenant.plan.slug, plan_slug)
                self.assertTrue(tenant.is_active)
                self.assertTrue(
                    Domain.objects.filter(tenant=tenant, domain=f'{slug}.localhost', is_primary=True).exists()
                )

                owner = User.objects.get(email=f'owner_{slug}@example.com')
                manager = User.objects.get(email=f'manager_{slug}@example.com')
                owner_membership = Membership.objects.get(user=owner, tenant=tenant, is_active=True)
                manager_membership = Membership.objects.get(user=manager, tenant=tenant, is_active=True)
                self.assertEqual(owner_membership.role, 'owner')
                self.assertEqual(manager_membership.role, 'manager')

            self.assertEqual(
                Membership.objects.filter(
                    tenant__slug__in=tuple(expected.keys()),
                    role__in=('owner', 'manager'),
                    is_active=True,
                ).count(),
                6,
            )

            admin = User.objects.get(email='platform_admin@example.com')
            self.assertTrue(admin.is_staff)
            self.assertTrue(admin.is_superuser)
            admin_membership = Membership.objects.get(user=admin, tenant__slug='org-crm', is_active=True)
            self.assertEqual(admin_membership.role, 'admin')

            # Keep fallback behaviour predictable for tests that rely on active tenant count.
            Tenant.objects.filter(slug__in=tuple(expected.keys())).update(is_active=False)

    def test_command_creates_users_for_existing_tenant(self):
        call_command(
            'create_test_users',
            '--tenant-slug',
            self.tenant.slug,
            '--password',
            'CommandPass123',
            '--reset-password',
        )

        with schema_context('public'):
            for role in ('owner', 'admin', 'manager', 'viewer'):
                email = f'{role}_{self.tenant.slug}@example.com'
                user = User.objects.get(email=email)
                membership = Membership.objects.get(user=user, tenant_id=self.tenant.id)
                self.assertTrue(user.check_password('CommandPass123'))
                self.assertEqual(membership.role, role)
                self.assertTrue(membership.is_active)
                self.assertIsNotNone(membership.joined_at)

            manager_user = User.objects.get(email=f'manager_{self.tenant.slug}@example.com')

        with tenant_context(self.tenant):
            from apps.integrations.models import ManagerProfile

            profile = ManagerProfile.objects.get(user_id=manager_user.id)
            self.assertTrue(profile.is_active)
            self.assertEqual(profile.crm_user_id, str(manager_user.id))

    def test_command_can_create_tenant_and_users(self):
        tenant_slug = f'qa-cmd-{uuid4().hex[:8]}'
        call_command(
            'create_test_users',
            '--tenant-slug',
            tenant_slug,
            '--create-tenant',
            '--tenant-name',
            'QA Command Tenant',
            '--plan-slug',
            'crm',
            '--password',
            'AutoCreate123',
        )

        with schema_context('public'):
            created_tenant = Tenant.objects.get(slug=tenant_slug)

            domain = Domain.objects.get(tenant=created_tenant, domain=f'{tenant_slug}.localhost')
            self.assertTrue(domain.is_primary)

            owner = User.objects.get(email=f'owner_{tenant_slug}@example.com')
            owner_membership = Membership.objects.get(user=owner, tenant=created_tenant)
            self.assertEqual(owner_membership.role, 'owner')
            self.assertTrue(owner.check_password('AutoCreate123'))

            # Keep fallback behaviour predictable for tests that rely on active tenant count.
            created_tenant.is_active = False
            created_tenant.save(update_fields=['is_active'])
