from django.contrib import admin
from .models import CRMConnection, WebhookEndpoint, ManagerProfile, ManagerDayOff, IntegrationErrorLog


@admin.register(CRMConnection)
class CRMConnectionAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'crm_type',
        'integration_mode',
        'is_active',
        'last_sync_at',
        'last_health_check_at',
        'last_webhook_at',
        'created_at',
    )
    list_filter = ('crm_type', 'integration_mode', 'is_active')


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'crm_connection', 'event_type', 'last_received_at', 'is_active')
    list_filter = ('is_active',)


@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = ('crm_user_name', 'user', 'crm_connection', 'is_active', 'max_active_deals')
    list_filter = ('is_active',)


@admin.register(ManagerDayOff)
class ManagerDayOffAdmin(admin.ModelAdmin):
    list_display = ('manager', 'date', 'reason')


@admin.register(IntegrationErrorLog)
class IntegrationErrorLogAdmin(admin.ModelAdmin):
    list_display = ('crm_connection', 'level', 'code', 'title', 'created_at')
    list_filter = ('level', 'code', 'crm_connection__crm_type')
