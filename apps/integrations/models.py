import uuid
from django.db import models
from apps.core.fields import EncryptedJSONField


class CRMConnection(models.Model):
    """Подключение к внешней CRM."""
    CRM_TYPES = [('amocrm', 'amoCRM'), ('bitrix24', 'Битрикс24')]
    INTEGRATION_MODES = [
        ('webhook', 'Webhook / Manual'),
        ('oauth', 'OAuth App'),
        ('marketplace', 'Marketplace App'),
    ]

    crm_type = models.CharField(max_length=20, choices=CRM_TYPES)
    name = models.CharField(max_length=200)
    credentials = EncryptedJSONField()
    integration_mode = models.CharField(max_length=20, choices=INTEGRATION_MODES, default='webhook')
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    last_webhook_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.crm_type})'


class WebhookEndpoint(models.Model):
    """Входящий вебхук от CRM."""
    crm_connection = models.ForeignKey(CRMConnection, on_delete=models.CASCADE, related_name='webhooks')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    event_type = models.CharField(max_length=100)
    secret_token = models.CharField(max_length=64)
    last_received_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.event_type} ({self.uuid})'


class ManagerProfile(models.Model):
    """Профиль менеджера в контексте тенанта."""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='+')
    crm_connection = models.ForeignKey(
        CRMConnection,
        on_delete=models.SET_NULL,
        related_name='managers',
        null=True,
        blank=True,
    )
    crm_user_id = models.CharField(max_length=100, blank=True)
    crm_user_name = models.CharField(max_length=200)
    max_active_deals = models.PositiveIntegerField(default=10)
    schedule = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.crm_user_name


class ManagerDayOff(models.Model):
    manager = models.ForeignKey(ManagerProfile, on_delete=models.CASCADE, related_name='days_off')
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'{self.manager} — {self.date}'


class IntegrationErrorLog(models.Model):
    """Пользовательский журнал проблем интеграции с шагами исправления."""

    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    crm_connection = models.ForeignKey(CRMConnection, on_delete=models.CASCADE, related_name='error_logs')
    code = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    message = models.TextField()
    resolution = models.TextField(blank=True, default='')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='error')
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.level}] {self.code} ({self.crm_connection_id})'
