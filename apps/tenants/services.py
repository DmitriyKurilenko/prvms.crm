"""Tenant lifecycle domain services.

Public surface for tenant provisioning. Other apps (users registration,
onboarding) compose tenant initialization through these helpers — never
import private symbols across app boundaries.
"""
from __future__ import annotations

import uuid

from django.utils.text import slugify
from django_tenants.utils import schema_context

from apps.tenants.models import Tenant

# Minimal Russian-Cyrillic to Latin transliteration table.
_CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def _transliterate(value: str) -> str:
    return ''.join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in value.lower())


def generate_tenant_slug(name: str, max_length: int = 50) -> str:
    """Create a URL-safe, unique tenant slug from an organization name.

    Covers Russian Cyrillic via a minimal transliteration table. Names written
    in other non-Latin scripts fall back to a generic 'org' base, with a
    numeric suffix guaranteeing uniqueness. The resulting slug always fits
    Django's default SlugField length limit.
    """
    raw = _transliterate(name.strip())
    base = slugify(raw).strip('-')
    if not base:
        base = 'org'

    # Reserve space for a uniqueness suffix (e.g. '-12345' or '-abc12').
    suffix_budget = 10
    base = base[: max(1, max_length - suffix_budget)].strip('-')
    if not base:
        base = 'org'

    candidate = base
    counter = 1
    while Tenant.objects.filter(slug=candidate).exists():
        suffix = f'-{counter}'
        candidate = f'{base[: max_length - len(suffix)]}{suffix}'
        counter += 1
        if counter > 9999:
            suffix = f'-{uuid.uuid4().hex[:8]}'
            candidate = f'{base[: max_length - len(suffix)]}{suffix}'
            break
    return candidate


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
    from apps.documents.seed import seed_system_templates_for_tenant
    from apps.notifications.services import seed_default_preferences

    with schema_context(tenant.schema_name):
        seed_default_preferences()
        ensure_default_pipeline()
        seed_system_templates_for_tenant(tenant)
