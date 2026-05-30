# Generated manually 2026-05-30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messenger_channels', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messengerchannel',
            name='channel_type',
            field=models.CharField(choices=[('telegram', 'Telegram Bot'), ('whatsapp_business', 'WhatsApp Business API'), ('whatsapp', 'WhatsApp (через провайдера)'), ('max', 'MAX'), ('vk', 'ВКонтакте')], max_length=20),
        ),
    ]
