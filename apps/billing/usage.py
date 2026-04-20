from __future__ import annotations

from django.utils import timezone
from django_tenants.utils import schema_context

from apps.contracts.models import Contract
from apps.crm.models import Pipeline
from apps.integrations.models import CRMConnection
from apps.users.models import Membership


MANAGER_LIMIT_ROLES = ('owner', 'admin', 'manager')


def get_plan_usage_for_tenant(tenant) -> dict[str, int]:
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with schema_context('public'):
        managers = Membership.objects.filter(
            tenant_id=tenant.id,
            is_active=True,
            role__in=MANAGER_LIMIT_ROLES,
            invite_token__isnull=True,
            joined_at__isnull=False,
        ).count()
    return {
        'managers': managers,
        'contracts': Contract.objects.filter(created_at__gte=month_start).count(),
        'crm_connections': CRMConnection.objects.filter(is_active=True).count(),
        'pipelines': Pipeline.objects.filter(is_active=True).count(),
    }
