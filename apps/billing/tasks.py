from __future__ import annotations

from celery import shared_task
from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Tenant
from .usage import get_plan_usage_for_tenant


def _percent(limit: int | None, value: int) -> float:
    if not limit:
        return 0.0
    if limit <= 0:
        return 0.0
    return (value / limit) * 100.0


@shared_task
def check_plan_limits():
    from apps.notifications.services import notify

    with schema_context('public'):
        tenants = list(Tenant.objects.select_related('plan').filter(is_active=True))

    results = []
    for tenant in tenants:
        with tenant_context(tenant):
            normalized_usage = get_plan_usage_for_tenant(tenant)
            usage = {
                'max_managers': normalized_usage['managers'],
                'max_documents_per_month': normalized_usage['documents'],
                'max_crm_connections': normalized_usage['crm_connections'],
                'max_pipelines': normalized_usage['pipelines'],
            }

            tenant_result = {'tenant_id': tenant.id, 'warnings': [], 'reached': []}
            for field, current in usage.items():
                limit = getattr(tenant.plan, field, None)
                if limit is None:
                    continue

                percent = _percent(limit, current)
                context = {
                    'limit_field': field,
                    'current': current,
                    'limit': limit,
                    'percent': round(percent, 2),
                }
                if current >= limit:
                    notify(
                        tenant,
                        'plan_limit_reached',
                        {
                            'message': f'Лимит {field} достигнут: {current}/{limit}',
                            **context,
                        },
                    )
                    tenant_result['reached'].append(context)
                elif percent >= 80:
                    notify(
                        tenant,
                        'plan_limit_warning',
                        {
                            'message': f'Лимит {field} близок к исчерпанию: {current}/{limit}',
                            **context,
                        },
                    )
                    tenant_result['warnings'].append(context)

            results.append(tenant_result)
    return results
