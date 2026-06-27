import uuid

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
    class Kind(models.TextChoices):
        PRESET = 'preset', 'Предустановленный'
        CUSTOM = 'custom', 'Конфигуратор'

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    features = models.ManyToManyField(Feature, related_name='plans', blank=True)
    max_managers = models.PositiveIntegerField(null=True, blank=True)
    max_documents_per_month = models.PositiveIntegerField(null=True, blank=True)
    max_pipelines = models.PositiveIntegerField(null=True, blank=True, default=1)
    # --- v2 pricing fields ---
    max_messengers = models.PositiveIntegerField(null=True, blank=True)
    max_inbound_channels = models.PositiveIntegerField(null=True, blank=True)
    max_signatures_per_month = models.PositiveIntegerField(null=True, blank=True)
    telephony_included = models.BooleanField(default=False)
    max_phone_numbers = models.PositiveIntegerField(null=True, blank=True)
    max_phone_lines = models.PositiveIntegerField(null=True, blank=True)
    included_minutes = models.PositiveIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PRESET)
    # -------------------------
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


class PricingQuote(models.Model):
    """Публичный расчёт СВОБОДНОГО тарифа с TTL 24ч."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    config = models.JSONField(default=dict)
    monthly_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    telephony_requires_quote = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


class TelephonyQuoteRequest(models.Model):
    """Заявка на телефонию для СВОБОДНОГО тарифа."""
    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        CONTACTED = 'contacted', 'Связались'
        CLOSED = 'closed', 'Закрыта'

    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    config_json = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'TelephonyQuoteRequest {self.name} ({self.status})'


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
