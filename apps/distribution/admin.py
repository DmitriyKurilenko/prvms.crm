from django.contrib import admin

from .models import DistributionLog, DistributionRule


@admin.register(DistributionRule)
class DistributionRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger', 'strategy', 'is_active', 'priority')
    list_filter = ('trigger', 'strategy', 'is_active')


@admin.register(DistributionLog)
class DistributionLogAdmin(admin.ModelAdmin):
    list_display = ('crm_entity_type', 'crm_entity_id', 'assigned_to', 'strategy_used', 'source', 'created_at')
    list_filter = ('source', 'strategy_used')
    readonly_fields = ('created_at',)
