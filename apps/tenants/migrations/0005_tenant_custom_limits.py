# Generated manually for plan pricing v2
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0004_add_sip_domain'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='custom_limits',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
