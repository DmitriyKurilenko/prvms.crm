import django.db.models.deletion
import encrypted_fields.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0001_initial'),
        ('telephony', '0002_alter_siptrunk_trunk_type'),
    ]

    operations = [
        # --- Drop FreeSWITCH coupling from CallRecord ---
        migrations.RemoveField(model_name='callrecord', name='sip_trunk'),
        migrations.RemoveField(model_name='callrecord', name='queue'),
        migrations.RenameField(model_name='callrecord', old_name='freeswitch_uuid', new_name='call_sid'),
        migrations.AlterField(
            model_name='callrecord',
            name='result',
            field=models.CharField(
                choices=[
                    ('answered', 'Отвечен'),
                    ('missed', 'Пропущен'),
                    ('busy', 'Занято'),
                    ('failed', 'Ошибка'),
                    ('voicemail', 'Голосовая почта'),
                ],
                default='missed',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='talk_time',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='cause_code',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='exolve_call_id',
            field=models.CharField(blank=True, max_length=64),
        ),
        # --- Remove FreeSWITCH models ---
        migrations.DeleteModel(name='CallQueue'),
        migrations.DeleteModel(name='IVRMenu'),
        migrations.DeleteModel(name='PhoneExtension'),
        migrations.DeleteModel(name='SIPTrunk'),
        # --- New Exolve models ---
        migrations.CreateModel(
            name='ExolveChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exolve_number', models.CharField(blank=True, help_text='Номер в формате E.164, например 79991112233', max_length=20)),
                ('number_code', models.CharField(blank=True, help_text='number_code номера в Exolve', max_length=20)),
                ('type_id', models.PositiveIntegerField(blank=True, null=True)),
                ('region_id', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Не подключён'), ('connecting', 'Подключение…'), ('active', 'Активен'), ('error', 'Ошибка'), ('disabled', 'Отключён')], default='draft', max_length=20)),
                ('status_detail', models.TextField(blank=True)),
                ('forwarding_set_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ExolveSIPAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sip_resource_id', models.CharField(blank=True, max_length=50)),
                ('username', models.CharField(blank=True, max_length=50)),
                ('password', encrypted_fields.fields.EncryptedCharField(blank=True, max_length=200)),
                ('display_number', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[('provisioning', 'Создаётся…'), ('active', 'Активен'), ('error', 'Ошибка'), ('disabled', 'Отключён')], default='provisioning', max_length=20)),
                ('status_detail', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('manager', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='exolve_sip', to='integrations.managerprofile')),
            ],
        ),
        migrations.AddConstraint(
            model_name='exolvesipaccount',
            constraint=models.UniqueConstraint(fields=('username',), name='unique_exolve_sip_username'),
        ),
    ]
