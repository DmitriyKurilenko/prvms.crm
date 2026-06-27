from __future__ import annotations

from django.utils import timezone
from django_tenants.utils import schema_context

from apps.channels.models import MessengerChannel
from apps.crm.models import Pipeline
from apps.documents.models import Document
from apps.users.models import Membership

MANAGER_LIMIT_ROLES = ('owner', 'admin', 'manager')

LIMIT_KEYS = {
    'managers': 'max_managers',
    'documents': 'max_documents_per_month',
    'pipelines': 'max_pipelines',
    'messengers': 'max_messengers',
    'inbound_channels': 'max_inbound_channels',
    'signatures': 'max_signatures_per_month',
}


def get_effective_limits(tenant):
    """Возвращает эффективные лимиты для тенанта (custom или из плана)."""
    if tenant.custom_limits:
        return tenant.custom_limits
    return {key: getattr(tenant.plan, attr) for key, attr in LIMIT_KEYS.items()}


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
        'documents': Document.objects.filter(created_at__gte=month_start).count(),
        'pipelines': Pipeline.objects.filter(is_active=True).count(),
        'messengers': MessengerChannel.objects.filter(is_active=True).count(),
        'inbound_channels': 0,  # placeholder until inbound channel model is available
        'signatures': 0,  # placeholder until signature counting is wired
    }
