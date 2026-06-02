# Generated manually for plan pricing v2 tenant migration
import logging
from decimal import Decimal

from django.db import migrations

logger = logging.getLogger(__name__)

PLAN_MAP = {
    'simple': 'solo',
    'basic': 'komanda',
    'crm': 'free-custom',
}


def migrate_forward(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Plan = apps.get_model('billing', 'Plan')
    Payment = apps.get_model('billing', 'Payment')

    # Pre-flight assertion
    for old_slug in PLAN_MAP.keys():
        count = Tenant.objects.filter(plan__slug=old_slug).count()
        logger.info(f'Migrating {count} tenants from plan={old_slug}')

    # Load target plans
    target_plans = {p.slug: p for p in Plan.objects.filter(slug__in=list(PLAN_MAP.values()))}

    for old_slug, new_slug in PLAN_MAP.items():
        new_plan = target_plans.get(new_slug)
        if not new_plan:
            logger.warning(f'Target plan {new_slug} not found, skipping {old_slug}')
            continue

        for tenant in Tenant.objects.filter(plan__slug=old_slug):
            old_plan = tenant.plan
            tenant.plan = new_plan

            if old_slug == 'crm':
                custom = tenant.custom_limits or {}
                custom['max_managers'] = old_plan.max_managers
                custom['max_contracts_per_month'] = old_plan.max_contracts_per_month
                custom['max_crm_connections'] = old_plan.max_crm_connections
                custom['max_pipelines'] = old_plan.max_pipelines
                tenant.custom_limits = custom

            # Preserve legacy pricing if tenant has active subscription
            has_active_payment = Payment.objects.filter(
                tenant=tenant,
                status='paid',
                expires_at__isnull=False,
            ).exists()
            if has_active_payment:
                custom = tenant.custom_limits or {}
                custom['legacy_pricing'] = {
                    'old_slug': old_slug,
                    'old_price': str(old_plan.price_monthly),
                }
                tenant.custom_limits = custom

            tenant.save(update_fields=['plan', 'custom_limits'])


def migrate_backward(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Plan = apps.get_model('billing', 'Plan')

    reverse_map = {v: k for k, v in PLAN_MAP.items()}
    for new_slug, old_slug in reverse_map.items():
        old_plan = Plan.objects.filter(slug=old_slug).first()
        if not old_plan:
            continue
        for tenant in Tenant.objects.filter(plan__slug=new_slug):
            tenant.plan = old_plan
            custom = tenant.custom_limits or {}
            # Remove legacy pricing marker if present
            if 'legacy_pricing' in custom:
                del custom['legacy_pricing']
            # Remove crm-specific custom limits if they match old plan fields
            if old_slug == 'crm':
                for key in ['max_managers', 'max_contracts_per_month', 'max_crm_connections', 'max_pipelines']:
                    custom.pop(key, None)
            tenant.custom_limits = custom
            tenant.save(update_fields=['plan', 'custom_limits'])


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0006_seed_plans_solo_komanda'),
        ('tenants', '0005_tenant_custom_limits'),
    ]

    operations = [
        migrations.RunPython(migrate_forward, migrate_backward),
    ]
