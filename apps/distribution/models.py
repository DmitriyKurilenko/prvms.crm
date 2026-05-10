from django.db import models


class DistributionRule(models.Model):
    """Правило распределения заявок."""
    TRIGGER_CHOICES = [
        ('new_deal', 'Новая сделка'),
    ]
    STRATEGY_CHOICES = [
        ('min_load', 'Минимальная нагрузка'),
        ('round_robin', 'По очереди'),
        ('weighted', 'Взвешенное'),
        ('manual_queue', 'Ручная очередь'),
    ]

    name = models.CharField(max_length=200)
    crm_connection = models.ForeignKey(
        'integrations.CRMConnection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    trigger_filter = models.JSONField(default=dict)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='min_load')
    strategy_config = models.JSONField(default=dict)
    managers = models.ManyToManyField(
        'integrations.ManagerProfile',
        related_name='distribution_rules',
        blank=True,
    )
    fallback_manager = models.ForeignKey(
        'integrations.ManagerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fallback_rules',
    )
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DistributionLog(models.Model):
    """Лог распределения. Кому, когда, почему."""
    SOURCE_CHOICES = [
        ('builtin_crm', 'Встроенная CRM'),
        ('crm_webhook', 'CRM-вебхук'),
        ('messenger', 'Мессенджер'),
        ('phone_call', 'Телефонный звонок'),
        ('manual', 'Ручное'),
    ]
    rule = models.ForeignKey(DistributionRule, on_delete=models.SET_NULL, null=True)
    crm_connection = models.ForeignKey(
        'integrations.CRMConnection',
        on_delete=models.SET_NULL,
        null=True,
    )
    crm_entity_type = models.CharField(max_length=20)
    crm_entity_id = models.CharField(max_length=100)
    assigned_to = models.ForeignKey(
        'integrations.ManagerProfile',
        on_delete=models.SET_NULL,
        null=True,
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='crm_webhook')
    strategy_used = models.CharField(max_length=20)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.crm_entity_type}:{self.crm_entity_id} → {self.assigned_to}'
