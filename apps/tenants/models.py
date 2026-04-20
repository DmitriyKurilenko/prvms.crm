import uuid

from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    plan = models.ForeignKey(
        'billing.Plan',
        on_delete=models.PROTECT,
        related_name='tenants',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Настройки ЛК организации
    logo = models.ImageField(upload_to='tenants/logos/', blank=True)
    brand_color = models.CharField(max_length=7, default='#570DF8')
    timezone = models.CharField(max_length=50, default='Europe/Moscow')
    language = models.CharField(max_length=5, default='ru')

    # CRM-режим
    crm_mode = models.CharField(
        max_length=20,
        choices=[
            ('builtin', 'Встроенный CRM'),
            ('bitrix24', 'Битрикс24'),
            ('amocrm', 'amoCRM'),
        ],
        default='builtin',
    )

    # SIP domain for per-tenant isolation (e.g. org-crm.sip.localhost)
    sip_domain = models.CharField(max_length=255, blank=True)

    # Онбординг
    onboarding_step = models.PositiveIntegerField(default=0)

    # Триал и оплата
    trial_expires_at = models.DateTimeField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)

    auto_create_schema = True

    @property
    def trial_active(self) -> bool:
        """True если триал ещё действует."""
        if self.is_paid:
            return False  # оплачено — не триал
        if not self.trial_expires_at:
            return False
        from django.utils import timezone as tz
        return tz.now() < self.trial_expires_at

    @property
    def trial_expired(self) -> bool:
        """True если триал закончился и нет оплаты."""
        if self.is_paid:
            return False
        if not self.trial_expires_at:
            return True  # нет триала и нет оплаты
        from django.utils import timezone as tz
        return tz.now() >= self.trial_expires_at

    @property
    def access_allowed(self) -> bool:
        """True если есть оплата или активный триал."""
        return self.is_paid or self.trial_active

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass


class SigningTokenLookup(models.Model):
    """Shared lookup for public signing URL -> tenant schema resolution."""

    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='signing_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.token} -> {self.tenant_id}'
