from django.apps import AppConfig


class ChannelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.channels'
    verbose_name = 'Мессенджер-каналы'
    label = 'messenger_channels'
