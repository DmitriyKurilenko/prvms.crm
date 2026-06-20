from __future__ import annotations

import sys
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify
from django_tenants.utils import schema_context, tenant_context

from apps.billing.models import Plan
from apps.tenants.models import Domain, Tenant
from apps.users.management._seed_common import reconcile_membership
from apps.users.models import Membership, User

ROLE_ORDER = ('owner', 'admin', 'manager', 'viewer')
BOOTSTRAP_ROLE_ORDER = ('owner', 'manager')
BOOTSTRAP_TENANTS = (
    ('org-solo', 'Demo Solo Org', 'solo'),
    ('org-komanda', 'Demo Komanda Org', 'komanda'),
    ('org-free', 'Demo Free Org', 'free-custom'),
)
PLATFORM_ADMIN_EMAIL = 'platform_admin@example.com'
PLATFORM_ADMIN_USERNAME = 'platform_admin'
PLATFORM_ADMIN_ROLE = 'admin'


@dataclass
class AccountResult:
    role: str
    email: str
    username: str
    created_user: bool
    created_membership: bool
    reset_password: bool
    user: User


class Command(BaseCommand):
    help = 'Creates deterministic test users for one tenant or bootstrap seed data when called without arguments.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-slug', required=False, help='Target tenant slug.')
        parser.add_argument('--password', default='Asdf2121', help='Password for created users.')
        parser.add_argument('--email-domain', default='example.com', help='Domain used for test user emails.')
        parser.add_argument('--username-prefix', default='qa', help='Prefix for generated usernames.')
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Reset password for existing users to --password value.',
        )
        parser.add_argument(
            '--create-tenant',
            action='store_true',
            help='Create tenant automatically when it does not exist.',
        )
        parser.add_argument('--tenant-name', default='', help='Tenant name when --create-tenant is used.')
        parser.add_argument('--plan-slug', default='komanda', help='Plan slug for auto-created tenant.')
        parser.add_argument(
            '--skip-manager-profile',
            action='store_true',
            help='Do not create/update ManagerProfile for manager account.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Allow running outside DEBUG environment.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force'] and not self._is_test_environment():
            raise CommandError('Command is disabled when DEBUG=False. Use --force to run explicitly.')

        raw_tenant_slug = str(options.get('tenant_slug') or '').strip().lower()
        if not raw_tenant_slug:
            self._bootstrap_seed(options)
            return

        tenant_slug = slugify(raw_tenant_slug)
        if not tenant_slug:
            raise CommandError('Invalid --tenant-slug value.')

        tenant = self._get_or_create_tenant(
            tenant_slug=tenant_slug,
            create_tenant=bool(options['create_tenant']),
            tenant_name=str(options['tenant_name']).strip(),
            plan_slug=str(options['plan_slug']).strip(),
            ensure_plan_for_existing=False,
        )
        password = str(options['password'])

        account_results = self._create_accounts_for_roles(
            tenant=tenant,
            roles=ROLE_ORDER,
            password=password,
            email_domain=str(options['email_domain']).strip(),
            username_prefix=str(options['username_prefix']).strip(),
            reset_password=bool(options['reset_password']),
        )

        manager_profile_status = 'skipped'
        if not options['skip_manager_profile']:
            manager_profile_status = self._ensure_manager_profile(
                tenant=tenant,
                manager_user=account_results['manager'].user,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Test users are ready for tenant "{tenant.slug}" (id={tenant.id}, schema={tenant.schema_name}).'
            )
        )
        self._print_role_results(account_results, ROLE_ORDER)

        password_set_count = self._count_password_sets(account_results)
        self._print_password_summary(
            password=password,
            password_set_count=password_set_count,
            total_accounts=len(ROLE_ORDER),
            sync_hint=(
                f'python manage.py create_test_users --tenant-slug {tenant.slug} '
                '--reset-password --password "<new-password>"'
            ),
        )
        self.stdout.write(f'Manager profile: {manager_profile_status}')

    def _bootstrap_seed(self, options: dict):
        self.stdout.write(
            self.style.WARNING(
                'No --tenant-slug provided: running bootstrap seed (3 tenants, 6 users, platform admin).'
            )
        )

        email_domain = str(options['email_domain']).strip()
        username_prefix = str(options['username_prefix']).strip()
        password = str(options['password'])
        reset_password = bool(options['reset_password'])
        skip_manager_profile = bool(options['skip_manager_profile'])

        tenant_summaries: list[tuple[Tenant, str, dict[str, AccountResult], str]] = []
        for slug, tenant_name, plan_slug in BOOTSTRAP_TENANTS:
            tenant = self._get_or_create_tenant(
                tenant_slug=slug,
                create_tenant=True,
                tenant_name=tenant_name,
                plan_slug=plan_slug,
                ensure_plan_for_existing=True,
            )
            account_results = self._create_accounts_for_roles(
                tenant=tenant,
                roles=BOOTSTRAP_ROLE_ORDER,
                password=password,
                email_domain=email_domain,
                username_prefix=username_prefix,
                reset_password=reset_password,
            )
            manager_profile_status = 'skipped'
            if not skip_manager_profile:
                manager_profile_status = self._ensure_manager_profile(
                    tenant=tenant,
                    manager_user=account_results['manager'].user,
                )
            tenant_summaries.append((tenant, plan_slug, account_results, manager_profile_status))

        admin_tenant = next((tenant for tenant, plan_slug, _, _ in tenant_summaries if plan_slug == 'komanda'), None)
        if admin_tenant is None and tenant_summaries:
            admin_tenant = tenant_summaries[0][0]

        admin_user, admin_created, admin_password_reset, admin_membership_status = self._ensure_platform_admin(
            password=password,
            reset_password=reset_password,
            tenant=admin_tenant,
        )

        self.stdout.write(self.style.SUCCESS('Bootstrap seed is ready.'))
        for tenant, plan_slug, account_results, manager_profile_status in tenant_summaries:
            self.stdout.write(
                f'- tenant "{tenant.slug}" (plan={plan_slug}, schema={tenant.schema_name}, id={tenant.id})'
            )
            self._print_role_results(account_results, BOOTSTRAP_ROLE_ORDER, indent='  ')
            self.stdout.write(f'  Manager profile: {manager_profile_status}')

        admin_flags = []
        admin_flags.append('user:new' if admin_created else 'user:existing')
        if admin_password_reset:
            admin_flags.append('password:set')
        self.stdout.write(
            f'- platform_admin {admin_user.email} '
            f'[{"; ".join(admin_flags)}; is_staff={admin_user.is_staff}; is_superuser={admin_user.is_superuser}]'
        )
        if admin_tenant is not None:
            self.stdout.write(
                f'  platform_admin membership: {admin_membership_status} '
                f'({admin_tenant.slug}/{PLATFORM_ADMIN_ROLE})'
            )
        bootstrap_account_count = len(BOOTSTRAP_TENANTS) * len(BOOTSTRAP_ROLE_ORDER) + 1
        bootstrap_password_set_count = int(admin_password_reset)
        for _, _, account_results, _ in tenant_summaries:
            bootstrap_password_set_count += self._count_password_sets(account_results)
        self._print_password_summary(
            password=password,
            password_set_count=bootstrap_password_set_count,
            total_accounts=bootstrap_account_count,
            sync_hint='python manage.py create_test_users --reset-password --password "<new-password>"',
        )

    def _get_or_create_tenant(
        self,
        *,
        tenant_slug: str,
        create_tenant: bool,
        tenant_name: str,
        plan_slug: str,
        ensure_plan_for_existing: bool,
    ) -> Tenant:
        with schema_context('public'):
            plan = Plan.objects.filter(slug=plan_slug, is_active=True).first()
            if not plan:
                raise CommandError(f'Plan "{plan_slug}" was not found or inactive.')

            default_domain = f'{tenant_slug}.localhost'
            conflicting_domain = Domain.objects.filter(domain=default_domain).exclude(tenant__slug=tenant_slug).first()
            if conflicting_domain:
                raise CommandError(
                    f'Domain "{default_domain}" already belongs to another tenant (id={conflicting_domain.tenant_id}).'
                )

            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if tenant:
                updates: list[str] = []
                if tenant_name and tenant.name != tenant_name:
                    tenant.name = tenant_name
                    updates.append('name')
                if ensure_plan_for_existing and tenant.plan_id != plan.id:
                    tenant.plan = plan
                    updates.append('plan')
                if not tenant.is_active:
                    tenant.is_active = True
                    updates.append('is_active')
                if tenant.crm_mode != 'builtin':
                    tenant.crm_mode = 'builtin'
                    updates.append('crm_mode')
                if updates:
                    tenant.save(update_fields=updates)

                self._ensure_default_domain(tenant=tenant, default_domain=default_domain)
                return tenant

            if not create_tenant:
                raise CommandError(
                    f'Tenant "{tenant_slug}" was not found. Use --create-tenant to create it automatically.'
                )

            tenant = Tenant(
                name=tenant_name or f'QA {tenant_slug}',
                slug=tenant_slug,
                schema_name=tenant_slug,
                plan=plan,
                crm_mode='builtin',
                is_active=True,
            )
            tenant.save()

            self._ensure_default_domain(tenant=tenant, default_domain=default_domain)

            return tenant

    @staticmethod
    def _ensure_default_domain(*, tenant: Tenant, default_domain: str):
        Domain.objects.filter(tenant=tenant, is_primary=True).exclude(domain=default_domain).update(is_primary=False)
        domain, created = Domain.objects.get_or_create(
            tenant=tenant,
            domain=default_domain,
            defaults={'is_primary': True},
        )
        if not created and not domain.is_primary:
            domain.is_primary = True
            domain.save(update_fields=['is_primary'])

    def _create_accounts_for_roles(
        self,
        *,
        tenant: Tenant,
        roles: tuple[str, ...] | list[str],
        password: str,
        email_domain: str,
        username_prefix: str,
        reset_password: bool,
    ) -> dict[str, AccountResult]:
        now = timezone.now()
        email_domain = email_domain.lower().strip()
        if not email_domain:
            raise CommandError('Invalid --email-domain value.')

        results: dict[str, AccountResult] = {}
        with schema_context('public'):
            for role in roles:
                email = f'{role}_{tenant.slug}@{email_domain}'
                username = self._build_username(username_prefix, role, tenant.slug)

                user, created_user = User.objects.get_or_create(
                    email=email,
                    defaults={'username': username},
                )
                if created_user and user.username != username:
                    user.username = username
                    user.save(update_fields=['username'])

                password_was_set = False
                if created_user or reset_password:
                    user.set_password(password)
                    user.save(update_fields=['password'])
                    password_was_set = True

                membership, created_membership = Membership.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={
                        'role': role,
                        'is_active': True,
                        'joined_at': now,
                    },
                )

                reconcile_membership(membership, role, now=now)

                results[role] = AccountResult(
                    role=role,
                    email=email,
                    username=user.username,
                    created_user=created_user,
                    created_membership=created_membership,
                    reset_password=password_was_set,
                    user=user,
                )

        return results

    def _ensure_platform_admin(
        self,
        *,
        password: str,
        reset_password: bool,
        tenant: Tenant | None,
    ) -> tuple[User, bool, bool, str]:
        with schema_context('public'):
            admin, created = User.objects.get_or_create(
                email=PLATFORM_ADMIN_EMAIL,
                defaults={
                    'username': PLATFORM_ADMIN_USERNAME,
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                },
            )

            updates: list[str] = []
            if admin.username != PLATFORM_ADMIN_USERNAME:
                admin.username = PLATFORM_ADMIN_USERNAME
                updates.append('username')
            if not admin.is_staff:
                admin.is_staff = True
                updates.append('is_staff')
            if not admin.is_superuser:
                admin.is_superuser = True
                updates.append('is_superuser')
            if not admin.is_active:
                admin.is_active = True
                updates.append('is_active')
            if updates:
                admin.save(update_fields=updates)

            password_reset = False
            if created or reset_password:
                admin.set_password(password)
                admin.save(update_fields=['password'])
                password_reset = True

            membership_status = 'skipped'
            if tenant is not None:
                membership, membership_created = Membership.objects.get_or_create(
                    user=admin,
                    tenant=tenant,
                    defaults={
                        'role': PLATFORM_ADMIN_ROLE,
                        'is_active': True,
                        'joined_at': timezone.now(),
                    },
                )
                membership_updates = reconcile_membership(membership, PLATFORM_ADMIN_ROLE, now=timezone.now())

                if membership_created:
                    membership_status = 'created'
                elif membership_updates:
                    membership_status = 'updated'
                else:
                    membership_status = 'existing'

            return admin, created, password_reset, membership_status

    def _ensure_manager_profile(self, *, tenant: Tenant, manager_user: User) -> str:
        with tenant_context(tenant):
            from apps.integrations.models import ManagerProfile

            _, created = ManagerProfile.objects.update_or_create(
                user=manager_user,
                defaults={
                    'crm_user_id': str(manager_user.id),
                    'crm_user_name': manager_user.username or manager_user.email,
                    'max_active_deals': 10,
                    'schedule': {},
                    'is_active': True,
                },
            )
            return 'created' if created else 'updated'

    @staticmethod
    def _build_username(prefix: str, role: str, tenant_slug: str) -> str:
        normalized_prefix = (prefix or 'qa').strip().replace('-', '_')
        normalized_slug = tenant_slug.replace('-', '_')
        return f'{normalized_prefix}_{role}_{normalized_slug}'

    def _print_role_results(
        self,
        account_results: dict[str, AccountResult],
        role_order: tuple[str, ...] | list[str],
        indent: str = '',
    ):
        for role in role_order:
            result = account_results[role]
            flags = []
            flags.append('user:new' if result.created_user else 'user:existing')
            flags.append('membership:new' if result.created_membership else 'membership:existing')
            flags.append('password:set' if result.reset_password else 'password:kept')
            self.stdout.write(
                f'{indent}- {role:<7} {result.email:<34} '
                f'(username={result.username}) '
                f'[{"; ".join(flags)}]'
            )

    @staticmethod
    def _count_password_sets(account_results: dict[str, AccountResult]) -> int:
        return sum(1 for result in account_results.values() if result.reset_password)

    def _print_password_summary(
        self,
        *,
        password: str,
        password_set_count: int,
        total_accounts: int,
        sync_hint: str,
    ) -> None:
        if password_set_count > 0:
            self.stdout.write(f'Password synchronized for {password_set_count}/{total_accounts} accounts: {password}')
            return

        self.stdout.write(
            self.style.WARNING('Passwords for existing accounts were preserved (run without --reset-password).')
        )
        self.stdout.write(self.style.WARNING(f'To synchronize passwords, run: {sync_hint}'))

    @staticmethod
    def _is_test_environment() -> bool:
        return 'test' in sys.argv
