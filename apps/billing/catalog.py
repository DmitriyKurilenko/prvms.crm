from __future__ import annotations

from apps.billing.models import Plan


def get_active_plans_queryset():
    return Plan.objects.filter(is_active=True).prefetch_related('features').order_by('sort_order', 'id')


def serialize_plan_for_client(plan: Plan) -> dict:
    return {
        'id': plan.id,
        'name': plan.name,
        'slug': plan.slug,
        'features': [
            {
                'code': feature.code,
                'name': feature.name,
                'description': feature.description,
            }
            for feature in plan.features.all().order_by('id')
        ],
        'max_managers': plan.max_managers,
        'max_contracts_per_month': plan.max_contracts_per_month,
        'max_crm_connections': plan.max_crm_connections,
        'max_pipelines': plan.max_pipelines,
        'price_monthly': float(plan.price_monthly),
        'is_active': plan.is_active,
    }
