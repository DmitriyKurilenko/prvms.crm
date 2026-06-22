from django.db import migrations


def backfill_task_reminder(apps, schema_editor):
    """Добавляет настройки нового события `task_reminder` тенантам, засеянным до
    его появления. `seed_default_preferences()` срабатывает один раз на схему и
    не дозаполняет новые события, поэтому существующим тенантам пара настроек
    (in_app включено, email выключено) создаётся идемпотентно здесь."""
    NotificationPreference = apps.get_model('notifications', 'NotificationPreference')
    # Дозаполняем только если в схеме уже есть какие-либо настройки (тенант засеян).
    if not NotificationPreference.objects.exists():
        return
    for channel, enabled in (('in_app', True), ('email', False)):
        NotificationPreference.objects.get_or_create(
            event='task_reminder',
            channel=channel,
            defaults={'is_enabled': enabled, 'recipient_roles': ['owner', 'admin']},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0003_alter_notification_event_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_task_reminder, noop_reverse),
    ]
