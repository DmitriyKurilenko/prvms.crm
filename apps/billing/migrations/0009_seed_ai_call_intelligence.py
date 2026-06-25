"""Фича `ai_call_intelligence` (транскрипция и резюме звонков, Фаза 2, DEC-056).

Гейтует распознавание записей звонков (Deepgram) и AI-резюме (Hermes). По
политике DEC-041/0008 активные планы получают модули, различаясь лимитами,
поэтому фича добавляется тем же целевым планам, что несут телефонию.
"""
from django.db import migrations

TARGET_PLAN_SLUGS = ['solo', 'komanda', 'free-custom']


def forward(apps, schema_editor):
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')
    feature, _ = Feature.objects.get_or_create(
        code='ai_call_intelligence',
        defaults={'name': 'AI-аналитика звонков', 'description': 'Транскрипция и резюме записей звонков'},
    )
    for plan in Plan.objects.filter(slug__in=TARGET_PLAN_SLUGS):
        plan.features.add(feature.id)


def backward(apps, schema_editor):
    Feature = apps.get_model('billing', 'Feature')
    Plan = apps.get_model('billing', 'Plan')
    fid = Feature.objects.filter(code='ai_call_intelligence').values_list('id', flat=True).first()
    if fid:
        for plan in Plan.objects.filter(slug__in=TARGET_PLAN_SLUGS):
            plan.features.remove(fid)


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_align_plan_features'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
