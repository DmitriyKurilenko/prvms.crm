from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django_tenants.utils import schema_context
from .models import Feature, Plan, Payment


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'description')
    search_fields = ('code', 'name')


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price_monthly', 'max_managers', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    filter_horizontal = ('features',)
    search_fields = ('name', 'slug')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'tenant', 'plan', 'amount', 'months', 'status', 'yookassa_payment_id', 'created_at', 'paid_at')
    list_filter = ('status',)
    search_fields = ('tenant__name', 'tenant__slug', 'yookassa_payment_id')
    readonly_fields = ('tenant', 'plan', 'amount', 'months', 'created_at', 'yookassa_payment_id', 'yookassa_confirmation_url')
    actions = ['confirm_payment']

    @admin.action(description='Ручное подтверждение оплаты (override)')
    def confirm_payment(self, request, queryset):
        for payment in queryset.filter(status='pending'):
            now = timezone.now()
            payment.status = 'paid'
            payment.paid_at = now
            payment.expires_at = now + timedelta(days=30 * payment.months)
            payment.save()

            with schema_context('public'):
                tenant = payment.tenant
                tenant.plan = payment.plan
                tenant.is_paid = True
                tenant.trial_expires_at = None
                tenant.save(update_fields=['plan', 'is_paid', 'trial_expires_at'])

        self.message_user(request, f'Подтверждено {queryset.count()} платеж(ей).')
