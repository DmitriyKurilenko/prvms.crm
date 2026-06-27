from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.billing.models import Plan
from apps.tenants.models import Domain, Tenant
from apps.tenants.services import provision_tenant
from apps.users.management._seed_common import reconcile_membership
from apps.users.models import Membership, User

DEFAULT_ROLES = ('owner', 'admin', 'manager')


class Command(BaseCommand):
    help = 'Seed N tenants with 3 users each + platform admin. Output format: email\\password'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of tenants (companies) to create.',
        )
        parser.add_argument(
            '--password',
            default='Asdf2121',
            help='Password for all created users.',
        )
        parser.add_argument(
            '--email-domain',
            default='test.ru',
            help='Domain used for emails.',
        )
        parser.add_argument(
            '--plan-slug',
            default='komanda',
            help='Plan slug for created tenants.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Allow running outside DEBUG environment.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError('Command is disabled when DEBUG=False. Use --force to run explicitly.')

        count = int(options['count'])
        if count < 1:
            raise CommandError('--count must be >= 1.')

        password = str(options['password'])
        email_domain = str(options['email_domain']).strip()
        plan_slug = str(options['plan_slug']).strip()

        with schema_context('public'):
            plan = Plan.objects.filter(slug=plan_slug, is_active=True).first()
            if not plan:
                raise CommandError(f'Plan "{plan_slug}" was not found or inactive.')

        accounts: list[tuple[str, str]] = []

        for i in range(1, count + 1):
            tenant_slug = f'company-{i}'
            tenant_name = f'Company {i}'
            tenant = self._get_or_create_tenant(
                tenant_slug=tenant_slug,
                tenant_name=tenant_name,
                plan=plan,
            )
            provision_tenant(tenant)

            for role_idx, role in enumerate(DEFAULT_ROLES):
                user_index = (i - 1) * len(DEFAULT_ROLES) + role_idx + 1
                email = f'test{user_index}@{email_domain}'
                username = f'test{user_index}'
                user = self._get_or_create_user(
                    email=email,
                    username=username,
                    password=password,
                )
                self._ensure_membership(user=user, tenant=tenant, role=role)
                accounts.append((email, password))

        # Platform admin
        admin_email = f'admin@{email_domain}'
        admin = self._get_or_create_user(
            email=admin_email,
            username='admin',
            password=password,
            is_staff=True,
            is_superuser=True,
        )
        first_tenant = Tenant.objects.filter(slug='company-1').first()
        if first_tenant:
            self._ensure_membership(user=admin, tenant=first_tenant, role='admin')
        accounts.append((admin_email, password))

        self.stdout.write(self.style.SUCCESS('Seed complete.'))
        self.stdout.write(self.style.WARNING(f'Total accounts: {len(accounts)}'))
        for email, pwd in accounts:
            self.stdout.write(f'{email}\\{pwd}')

    def _get_or_create_tenant(self, tenant_slug: str, tenant_name: str, plan: Plan) -> Tenant:
        with schema_context('public'):
            default_domain = f'{tenant_slug}.localhost'
            trial_expires = timezone.now() + timedelta(days=30)

            # Ensure no other tenant owns this domain as primary
            Domain.objects.filter(
                tenant__slug=tenant_slug,
                is_primary=True,
            ).exclude(domain=default_domain).update(is_primary=False)

            tenant, created = Tenant.objects.get_or_create(
                slug=tenant_slug,
                defaults={
                    'name': tenant_name,
                    'schema_name': tenant_slug,
                    'plan': plan,
                    'is_active': True,
                    'trial_expires_at': trial_expires,
                },
            )
            if not created:
                updates: list[str] = []
                if tenant.name != tenant_name:
                    tenant.name = tenant_name
                    updates.append('name')
                if tenant.plan_id != plan.id:
                    tenant.plan = plan
                    updates.append('plan')
                if not tenant.is_active:
                    tenant.is_active = True
                    updates.append('is_active')
                if tenant.trial_expires_at is None or tenant.trial_expires_at < timezone.now():
                    tenant.trial_expires_at = trial_expires
                    updates.append('trial_expires_at')
                if updates:
                    tenant.save(update_fields=updates)

            domain, _ = Domain.objects.get_or_create(
                tenant=tenant,
                domain=default_domain,
                defaults={'is_primary': True},
            )
            if not domain.is_primary:
                domain.is_primary = True
                domain.save(update_fields=['is_primary'])

            return tenant

    def _get_or_create_user(
        self,
        email: str,
        username: str,
        password: str,
        is_staff: bool = False,
        is_superuser: bool = False,
    ) -> User:
        with schema_context('public'):
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': username,
                    'is_staff': is_staff,
                    'is_superuser': is_superuser,
                    'is_active': True,
                },
            )
            updates: list[str] = []
            if not created:
                if user.username != username:
                    user.username = username
                    updates.append('username')
                if user.is_staff != is_staff:
                    user.is_staff = is_staff
                    updates.append('is_staff')
                if user.is_superuser != is_superuser:
                    user.is_superuser = is_superuser
                    updates.append('is_superuser')
                if not user.is_active:
                    user.is_active = True
                    updates.append('is_active')
                if updates:
                    user.save(update_fields=updates)

            # Always synchronize password for deterministic seeding
            user.set_password(password)
            user.save(update_fields=['password'])
            return user

    def _ensure_membership(self, user: User, tenant: Tenant, role: str) -> None:
        with schema_context('public'):
            now = timezone.now()
            membership, _ = Membership.objects.get_or_create(
                user=user,
                tenant=tenant,
                defaults={
                    'role': role,
                    'is_active': True,
                    'joined_at': now,
                },
            )
            reconcile_membership(membership, role, now=now)
