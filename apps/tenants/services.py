"""Tenant lifecycle domain services.

Public surface for tenant provisioning. Other apps (users registration,
onboarding) compose tenant initialization through these helpers — never
import private symbols across app boundaries.
"""
from __future__ import annotations

from django_tenants.utils import schema_context

from apps.tenants.models import Tenant


DEFAULT_PIPELINE_STAGES = (
    ('Новая заявка', 'open', '#3B82F6', 0),
    ('Квалификация', 'open', '#8B5CF6', 1),
    ('Предложение', 'open', '#F59E0B', 2),
    ('Переговоры', 'open', '#EF4444', 3),
    ('Согласование', 'open', '#10B981', 4),
    ('Успешно закрыта', 'won', '#22C55E', 5),
    ('Проиграна', 'lost', '#6B7280', 6),
)


def ensure_default_pipeline() -> None:
    """Create a default sales pipeline with typical stages if none exists.

    Idempotent: noop when at least one pipeline already exists in the
    current schema. Caller is expected to be inside the correct
    schema_context.
    """
    from apps.crm.models import Pipeline, Stage

    if Pipeline.objects.exists():
        return

    pipeline = Pipeline.objects.create(name='Продажи', is_default=True, sort_order=0)
    Stage.objects.bulk_create([
        Stage(pipeline=pipeline, name=name, stage_type=stype, color=color, sort_order=order)
        for name, stype, color, order in DEFAULT_PIPELINE_STAGES
    ])


def provision_tenant(tenant: Tenant) -> None:
    """Initialize per-tenant defaults right after tenant + schema creation.

    Called from registration and onboarding-skip flows. Adding new
    provisioning steps (default integrations, RBAC matrices, etc.) should
    go here, not be scattered across API modules.
    """
    from apps.notifications.services import seed_default_preferences

    with schema_context(tenant.schema_name):
        seed_default_preferences()
        ensure_default_pipeline()
