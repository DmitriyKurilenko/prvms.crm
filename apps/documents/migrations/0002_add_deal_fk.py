# Generated manually to break the circular dependency between documents and crm.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
        ('crm', '0005_add_esign_agreement_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='deal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents',
                to='crm.deal',
            ),
        ),
    ]
