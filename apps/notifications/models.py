from django.db import models


class NotificationChannel(models.TextChoices):
    EMAIL = 'email', 'Email'
    IN_APP = 'in_app', 'In-App'
    TELEGRAM = 'telegram', 'Telegram'


class NotificationEvent(models.TextChoices):
    DOCUMENT_SIGNED = 'document_signed', 'Документ подписан'
    LEAD_DISTRIBUTED = 'lead_distributed', 'Заявка распределена'
    CRM_CONNECTION_LOST = 'crm_connection_lost', 'CRM-соединение потеряно'
    CRM_CONNECTION_RESTORED = 'crm_connection_restored', 'CRM-соединение восстановлено'
    PLAN_LIMIT_WARNING = 'plan_limit_warning', 'Лимит плана на исходе (80%)'
    PLAN_LIMIT_REACHED = 'plan_limit_reached', 'Лимит плана достигнут'
    USER_INVITED = 'user_invited', 'Пользователь приглашён'
    MANAGER_SYNC_DONE = 'manager_sync_done', 'Синхронизация менеджеров завершена'
    SIGNING_EXPIRED = 'signing_expired', 'Срок подписания истёк'
    DEAL_STAGE_CHANGED = 'deal_stage_changed', 'Сделка перемещена'
    TASK_OVERDUE = 'task_overdue', 'Задача просрочена'
    TASK_REMINDER = 'task_reminder', 'Напоминание о задаче'
    NEW_DEAL_CREATED = 'new_deal_created', 'Новая сделка создана'


class NotificationPreference(models.Model):
    """Настройки уведомлений на уровне тенанта."""
    event = models.CharField(max_length=50, choices=NotificationEvent.choices)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    is_enabled = models.BooleanField(default=True)
    recipient_roles = models.JSONField(
        default=list,
        help_text='["owner", "admin", "manager"] — пустой список = owner+admin',
    )

    class Meta:
        unique_together = ['event', 'channel']

    def __str__(self):
        return f'{self.event} via {self.channel}'


class Notification(models.Model):
    """Конкретное уведомление для пользователя."""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    event = models.CharField(max_length=50, choices=NotificationEvent.choices)
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.title} → {self.user.email}'


class TelegramBinding(models.Model):
    """Привязка Telegram-аккаунта к пользователю для уведомлений."""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE, related_name='telegram')
    chat_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'TG:{self.username or self.chat_id} → {self.user.email}'
