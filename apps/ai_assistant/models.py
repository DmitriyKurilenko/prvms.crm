from django.db import models


class AIConversation(models.Model):
    """Диалог пользователя с AI-ассистентом.

    Живёт в tenant schema — изоляция по тенанту обеспечивается схемой,
    отдельный FK на Tenant не нужен.
    """
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='ai_conversations',
    )
    channel = models.ForeignKey(
        'messenger_channels.ChatSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_conversations',
    )
    deal = models.ForeignKey(
        'crm.Deal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_conversations',
    )
    title = models.CharField(max_length=200, blank=True)
    hermes_conversation_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'AI Conversation {self.id} - {self.user.email}'


class AIMessage(models.Model):
    """Сообщение в диалоге с AI."""
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('assistant', 'AI Ассистент'),
        ('system', 'Системное'),
    ]
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.role}: {self.content[:50]}...'
