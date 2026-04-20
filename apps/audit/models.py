from django.db import models


class AuditEvent(models.Model):
    """Лог действий пользователей. Неизменяемая таблица (append-only)."""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('invite', 'Invite'),
        ('sign', 'Sign'),
        ('distribute', 'Distribute'),
        ('sync', 'Sync'),
        ('export', 'Export'),
    ]

    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'{self.action} {self.model_name} by {self.user_id} at {self.created_at}'
