# Generated manually on 2026-04-13
from django.db import migrations


FEATURES = [
    ('distribution', 'Распределение заявок'),
    ('contracts', 'Создание договоров'),
    ('contract_signing', 'Онлайн-подписание (OTP)'),
    ('crm_bitrix24', 'Интеграция с Битрикс24'),
    ('crm_amocrm', 'Интеграция с amoCRM'),
    ('analytics', 'Дашборд и аналитика'),
    ('export_pdf', 'Экспорт отчётов в PDF'),
    ('export_excel', 'Экспорт отчётов в Excel'),
    ('custom_contract_templates', 'Собственные шаблоны договоров'),
    ('api_access', 'Доступ к API'),
    ('messenger_channels', 'Мессенджер-каналы'),
    ('telephony', 'Телефония'),
    ('crm_builtin', 'Встроенный CRM'),
]


PLANS = [
    {
        'slug': 'simple',
        'name': 'Простая',
        'price_monthly': '0.00',
        'sort_order': 10,
        'max_managers': 3,
        'max_contracts_per_month': 20,
        'max_crm_connections': 1,
        'max_pipelines': 1,
        'features': ['contracts', 'contract_signing'],
    },
    {
        'slug': 'basic',
        'name': 'Базовая',
        'price_monthly': '4990.00',
        'sort_order': 20,
        'max_managers': 10,
        'max_contracts_per_month': 200,
        'max_crm_connections': 1,
        'max_pipelines': 2,
        'features': [
            'contracts',
            'contract_signing',
            'distribution',
            'analytics',
            'custom_contract_templates',
            'export_pdf',
            'api_access',
        ],
    },
    {
        'slug': 'crm',
        'name': 'CRM',
        'price_monthly': '12990.00',
        'sort_order': 30,
        'max_managers': None,
        'max_contracts_per_month': None,
        'max_crm_connections': 3,
        'max_pipelines': None,
        'features': [code for code, _ in FEATURES],
    },
]


def seed_forward(apps, schema_editor):
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')

    feature_by_code = {}
    for code, name in FEATURES:
        feature, _ = Feature.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'description': '',
            },
        )
        feature_by_code[code] = feature

    for raw_plan in PLANS:
        plan_data = dict(raw_plan)
        features = plan_data.pop('features')
        plan, _ = Plan.objects.update_or_create(slug=plan_data['slug'], defaults=plan_data)
        plan.features.set([feature_by_code[item] for item in features])


def seed_backward(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    Feature = apps.get_model('billing', 'Feature')

    slugs = [plan['slug'] for plan in PLANS]
    codes = [code for code, _ in FEATURES]

    Plan.objects.filter(slug__in=slugs).delete()
    Feature.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]
