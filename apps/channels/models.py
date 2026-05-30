from django.db import models
from apps.core.fields import EncryptedJSONField


class MessengerChannel(models.Model):
    """Мессенджер-канал, привязанный к CRM-подключению."""
    CHANNEL_TYPE_CHOICES = [
        ('telegram', 'Telegram Bot'),
        ('whatsapp_business', 'WhatsApp Business API'),
        ('whatsapp', 'WhatsApp (через провайдера)'),
        ('max', 'MAX'),
        ('vk', 'ВКонтакте'),
    ]
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('error', 'Ошибка'),
        ('disabled', 'Отключён'),
    ]

    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPE_CHOICES)
    crm_connection = models.ForeignKey(
        'integrations.CRMConnection',
        on_delete=models.SET_NULL,
        related_name='messenger_channels',
        null=True,
        blank=True,
    )
    credentials = EncryptedJSONField()
    crm_channel_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    status_detail = models.TextField(blank=True)
    auto_create_lead = models.BooleanField(default=True)
    welcome_message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.channel_type})'


class ChatSession(models.Model):
    """Сессия чата: связь между внешним чатом и сущностью CRM."""
    channel = models.ForeignKey(MessengerChannel, on_delete=models.CASCADE, related_name='chat_sessions')
    external_chat_id = models.CharField(max_length=200)
    external_user_name = models.CharField(max_length=200, blank=True)
    crm_contact_id = models.CharField(max_length=100, blank=True)
    crm_chat_id = models.CharField(max_length=200, blank=True)
    crm_lead_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['channel', 'external_chat_id']

    def __str__(self):
        return f'{self.external_user_name or self.external_chat_id} @ {self.channel}'


class MessageLog(models.Model):
    """Лог сообщений. Для отладки и аудита."""
    DIRECTION_CHOICES = [
        ('in', 'Входящее'),
        ('out', 'Исходящее'),
    ]
    chat_session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    text = models.TextField(blank=True)
    attachments = models.JSONField(default=list)
    external_message_id = models.CharField(max_length=200, blank=True)
    crm_message_id = models.CharField(max_length=200, blank=True)
    delivered = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.direction} @ {self.created_at}'
