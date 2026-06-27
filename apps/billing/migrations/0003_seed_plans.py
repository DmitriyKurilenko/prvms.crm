"""Сид тарифов и фич (консолидировано после рефакторинга «команда»/удаления внешних CRM).

Продукт — единая встроенная CRM, поэтому все активные планы получают полный набор
канонических фич, которые проверяет приложение (`require_feature_access`,
меню, `useFeatureGate`); тарифы различаются лимитами `max_*`, а не скрытием модулей.
Внешне-CRM-фичи (`crm_amocrm`/`crm_bitrix24`) намеренно отсутствуют.
"""
from django.db import migrations

# Канонические коды фич, реально проверяемые приложением.
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
    ('ai_call_intelligence', 'AI-аналитика звонков'),
]

PLANS = [
    {
        'slug': 'solo', 'name': 'СОЛО', 'sort_order': 10, 'price_monthly': '2990.00',
        'description': 'Для индивидуальных предпринимателей и малого бизнеса',
        'max_managers': 1, 'max_documents_per_month': 100, 'max_pipelines': 1,
        'max_messengers': 2, 'max_inbound_channels': 1, 'max_signatures_per_month': 20,
        'telephony_included': False,
    },
    {
        'slug': 'komanda', 'name': 'КОМАНДА', 'sort_order': 20, 'price_monthly': '5990.00',
        'description': 'Для команд продаж с телефонией и автоматизацией',
        'max_managers': 5, 'max_documents_per_month': 1000, 'max_pipelines': 2,
        'max_messengers': 3, 'max_inbound_channels': 3, 'max_signatures_per_month': 100,
        'telephony_included': True, 'max_phone_numbers': 1, 'max_phone_lines': 5,
        'included_minutes': 1000,
    },
    {
        'slug': 'free-custom', 'name': 'СВОБОДНЫЙ', 'sort_order': 30, 'price_monthly': '0.00',
        'description': 'Конфигурируемый тариф: платите только за нужные ресурсы',
        'max_managers': None, 'max_documents_per_month': None, 'max_pipelines': 1,
        'kind': 'custom', 'is_active': True,
    },
]


def forward(apps, schema_editor):
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')

    feature_ids = []
    for code, name in CANONICAL_FEATURES:
        feature, _ = Feature.objects.get_or_create(code=code, defaults={'name': name, 'description': ''})
        feature_ids.append(feature.id)

    for raw in PLANS:
        plan, _ = Plan.objects.update_or_create(slug=raw['slug'], defaults=dict(raw))
        plan.features.set(feature_ids)


def backward(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    Plan.objects.filter(slug__in=[p['slug'] for p in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
