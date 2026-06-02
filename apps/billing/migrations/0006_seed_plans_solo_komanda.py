# Generated manually for plan pricing v2 seed
from django.db import migrations


NEW_FEATURES = [
    ('messenger_telegram', 'Мессенджер Telegram'),
    ('messenger_vk', 'Мессенджер ВКонтакте'),
    ('messenger_max', 'Мессенджер MAX'),
    ('messenger_whatsapp', 'Мессенджер WhatsApp'),
    ('channel_vk', 'Канал ВКонтакте'),
    ('channel_avito', 'Канал Авито'),
    ('channel_site_widget', 'Канал Сайт/виджет'),
    ('channel_email', 'Канал Email'),
    ('telephony_basic', 'Базовая телефония'),
    ('contracts_basic', 'Базовые договоры'),
    ('email_notifications', 'Email-уведомления'),
    ('crm_builtin', 'Встроенный CRM'),
]

SOLO_FEATURES = [
    'messenger_telegram',
    'messenger_vk',
    'email_notifications',
    'channel_vk',
    'contracts_basic',
    'crm_builtin',
]

KOMANDA_FEATURES = SOLO_FEATURES + [
    'messenger_max',
    'channel_avito',
    'channel_site_widget',
    'telephony_basic',
    'distribution',
]

PLANS = [
    {
        'slug': 'solo',
        'name': 'СОЛО',
        'description': 'Для индивидуальных предпринимателей и малого бизнеса',
        'price_monthly': '2990.00',
        'sort_order': 10,
        'max_managers': 1,
        'max_contracts_per_month': 100,
        'max_crm_connections': 1,
        'max_pipelines': 1,
        'max_messengers': 2,
        'max_inbound_channels': 1,
        'max_signatures_per_month': 20,
        'telephony_included': False,
        'features': SOLO_FEATURES,
    },
    {
        'slug': 'komanda',
        'name': 'КОМАНДА',
        'description': 'Для команд продаж с телефонией и автоматизацией',
        'price_monthly': '5990.00',
        'sort_order': 20,
        'max_managers': 5,
        'max_contracts_per_month': 1000,
        'max_crm_connections': 1,
        'max_pipelines': 2,
        'max_messengers': 3,
        'max_inbound_channels': 3,
        'max_signatures_per_month': 100,
        'telephony_included': True,
        'max_phone_numbers': 1,
        'max_phone_lines': 5,
        'included_minutes': 1000,
        'features': KOMANDA_FEATURES,
    },
    {
        'slug': 'free-custom',
        'name': 'СВОБОДНЫЙ',
        'description': 'Конфигурируемый тариф: платите только за нужные ресурсы',
        'price_monthly': '0.00',
        'sort_order': 30,
        'max_managers': None,
        'max_contracts_per_month': None,
        'max_crm_connections': 1,
        'max_pipelines': 1,
        'kind': 'custom',
        'is_active': True,
        'features': [],
    },
]

LEGACY_SLUGS = ['simple', 'basic', 'crm']


def seed_forward(apps, schema_editor):
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')

    # Load existing features + seed new ones
    feature_by_code = {f.code: f for f in Feature.objects.all()}
    for code, name in NEW_FEATURES:
        if code not in feature_by_code:
            feature = Feature.objects.create(code=code, name=name, description='')
            feature_by_code[code] = feature

    # Seed new plans
    for raw_plan in PLANS:
        plan_data = dict(raw_plan)
        feature_codes = plan_data.pop('features')
        plan, _ = Plan.objects.update_or_create(
            slug=plan_data['slug'],
            defaults=plan_data,
        )
        if feature_codes:
            plan.features.set([feature_by_code[c] for c in feature_codes])
        else:
            plan.features.clear()

    # Deactivate legacy plans
    Plan.objects.filter(slug__in=LEGACY_SLUGS).update(is_active=False)


def seed_backward(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    Feature = apps.get_model('billing', 'Feature')

    # Delete seeded plans
    slugs = [p['slug'] for p in PLANS]
    Plan.objects.filter(slug__in=slugs).delete()

    # Delete seeded features
    codes = [code for code, _ in NEW_FEATURES]
    Feature.objects.filter(code__in=codes).delete()

    # Reactivate legacy plans
    Plan.objects.filter(slug__in=LEGACY_SLUGS).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0005_plan_pricing_v2'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]
