# Generated manually for plan pricing v2
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0004_add_yookassa_fields'),
    ]

    operations = [
        # Plan v2 fields
        migrations.AddField(
            model_name='plan',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='max_messengers',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='max_inbound_channels',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='max_signatures_per_month',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='telephony_included',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='plan',
            name='max_phone_numbers',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='max_phone_lines',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='included_minutes',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plan',
            name='kind',
            field=models.CharField(
                choices=[('preset', 'Предустановленный'), ('custom', 'Конфигуратор')],
                default='preset',
                max_length=10,
            ),
        ),
        # PricingQuote
        migrations.CreateModel(
            name='PricingQuote',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('config', models.JSONField(default=dict)),
                ('monthly_total', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('telephony_requires_quote', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        # TelephonyQuoteRequest
        migrations.CreateModel(
            name='TelephonyQuoteRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('config_json', models.JSONField(default=dict)),
                ('status', models.CharField(choices=[('new', 'Новая'), ('contacted', 'Связались'), ('closed', 'Закрыта')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
