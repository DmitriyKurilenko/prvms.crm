from django.db import models


class Feature(models.Model):
    """Атомарная функция платформы. Создаётся и управляется только админом платформы."""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Plan(models.Model):
    """Тарифный план. Определяет набор доступных функций и лимиты."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    features = models.ManyToManyField(Feature, related_name='plans', blank=True)
    max_managers = models.PositiveIntegerField(null=True, blank=True)
    max_contracts_per_month = models.PositiveIntegerField(null=True, blank=True)
    max_crm_connections = models.PositiveIntegerField(null=True, blank=True, default=1)
    max_pipelines = models.PositiveIntegerField(null=True, blank=True, default=1)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return self.name

    def has_feature(self, feature_code: str) -> bool:
        return self.features.filter(code=feature_code).exists()


class Payment(models.Model):
    """Платёж за подписку через ЮKassa."""
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('cancelled', 'Отменён'),
        ('refunded', 'Возврат'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='payments',
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    months = models.PositiveIntegerField(default=1)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    yookassa_payment_id = models.CharField(max_length=50, blank=True, db_index=True)
    yookassa_confirmation_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment #{self.id} — {self.tenant} — {self.status}'
