"""Migrate responsible FK from integrations.ManagerProfile to users.User.

Steps:
1. Add temp responsible_user FK to User on Deal, Activity, Contact, Company
2. Copy ManagerProfile.user_id → responsible_user_id for every existing row
3. Drop indexes referencing old responsible field
4. Remove old responsible FK (to ManagerProfile)
5. Rename responsible_user → responsible
6. Re-add indexes on new responsible field
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def translate_responsible(apps, schema_editor):
    """For each CRM entity, look up ManagerProfile.user_id and set responsible_user_id."""
    ManagerProfile = apps.get_model('integrations', 'ManagerProfile')
    mp_to_user = dict(ManagerProfile.objects.values_list('id', 'user_id'))

    for model_name in ('Deal', 'Activity', 'Contact', 'Company'):
        Model = apps.get_model('crm', model_name)
        rows = Model.objects.filter(responsible__isnull=False).only('id', 'responsible_id')
        for row in rows:
            user_id = mp_to_user.get(row.responsible_id)
            if user_id:
                Model.objects.filter(id=row.id).update(responsible_user_id=user_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_initial'),
        ('integrations', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add temp FK fields
        migrations.AddField(
            model_name='deal',
            name='responsible_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='activity',
            name='responsible_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='responsible_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='responsible_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # 2. Copy data
        migrations.RunPython(translate_responsible, noop),

        # 3. Drop indexes that reference old responsible
        migrations.RemoveIndex(
            model_name='activity',
            name='crm_activit_respons_2e2b4f_idx',
        ),
        migrations.RemoveIndex(
            model_name='deal',
            name='crm_deal_respons_11d868_idx',
        ),

        # 4. Remove old responsible FK (to ManagerProfile)
        migrations.RemoveField(model_name='deal', name='responsible'),
        migrations.RemoveField(model_name='activity', name='responsible'),
        migrations.RemoveField(model_name='contact', name='responsible'),
        migrations.RemoveField(model_name='company', name='responsible'),

        # 5. Rename temp → responsible
        migrations.RenameField(model_name='deal', old_name='responsible_user', new_name='responsible'),
        migrations.RenameField(model_name='activity', old_name='responsible_user', new_name='responsible'),
        migrations.RenameField(model_name='contact', old_name='responsible_user', new_name='responsible'),
        migrations.RenameField(model_name='company', old_name='responsible_user', new_name='responsible'),

        # 6. Alter fields to match model definition (related_name)
        migrations.AlterField(
            model_name='deal',
            name='responsible',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_deals',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='activity',
            name='responsible',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_activities',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='contact',
            name='responsible',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_contacts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='company',
            name='responsible',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_companies',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # 7. Re-add indexes
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(fields=['responsible', 'status', '-due_date'], name='crm_activit_respons_user_idx'),
        ),
        migrations.AddIndex(
            model_name='deal',
            index=models.Index(fields=['responsible', '-updated_at'], name='crm_deal_respons_user_idx'),
        ),
    ]
