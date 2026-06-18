"""Выровнять фичи планов под канонические коды, которые проверяет приложение.

DEC-041 (сид v2-планов) выдал планам коды `documents_basic`/`messenger_telegram`/
`telephony_basic`, которых нет в гейтинге приложения (меню, роутер,
`require_feature_access`, `useFeatureGate` проверяют `documents`/`messenger_channels`/
`telephony`/`crm_builtin` и т.д.). Из-за этого разделы «Документы/Чаты/Телефония"
оставались заблокированными даже на КОМАНДА, а у `free-custom` фич не было вовсе.

Политика: продукт — единая встроенная CRM, поэтому все активные планы получают
полный набор разделов; тарифы различаются лимитами (`max_*`), а не скрытием модулей.
`has_feature` читает M2M вживую, поэтому правка немедленно разблокирует всех тенантов.
"""
from django.db import migrations

# Канонические коды фич, которые реально проверяет приложение
# (внешние CRM crm_bitrix24/crm_amocrm намеренно исключены — продукт только builtin).
CANONICAL_FEATURES = [
    ('crm_builtin', 'Встроенный CRM'),
    ('messenger_channels', 'Мессенджер-каналы'),
    ('documents', 'Документы'),
    ('document_signing', 'Подписание документов'),
    ('telephony', 'Телефония'),
    ('analytics', 'Аналитика и дашборды'),
    ('distribution', 'Распределение заявок'),
    ('export_pdf', 'Экспорт в PDF'),
    ('export_excel', 'Экспорт в Excel'),
    ('custom_document_templates', 'Свои шаблоны документов'),
    ('api_access', 'Доступ к API'),
]

TARGET_PLAN_SLUGS = ['solo', 'komanda', 'free-custom']


def forward(apps, schema_editor):
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')

    feature_ids = []
    for code, name in CANONICAL_FEATURES:
        feature, _ = Feature.objects.get_or_create(code=code, defaults={'name': name, 'description': ''})
        feature_ids.append(feature.id)

    for plan in Plan.objects.filter(slug__in=TARGET_PLAN_SLUGS):
        plan.features.add(*feature_ids)


def backward(apps, schema_editor):
    # Снимаем только канонические коды с целевых планов (исходное состояние сида).
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')
    feature_ids = list(
        Feature.objects.filter(code__in=[c for c, _ in CANONICAL_FEATURES]).values_list('id', flat=True)
    )
    for plan in Plan.objects.filter(slug__in=TARGET_PLAN_SLUGS):
        plan.features.remove(*feature_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_migrate_tenants_to_v2_plans'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
