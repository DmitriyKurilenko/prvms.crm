from django.contrib import admin

from .models import CallRecord, ExolveChannel, ExolveSIPAccount


@admin.register(ExolveChannel)
class ExolveChannelAdmin(admin.ModelAdmin):
    list_display = ('exolve_number', 'number_code', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active')


@admin.register(ExolveSIPAccount)
class ExolveSIPAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'manager', 'display_number', 'status', 'is_active')
    list_filter = ('status', 'is_active')


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = ('direction', 'caller_number', 'called_number', 'result', 'duration', 'started_at')
    list_filter = ('direction', 'result')
    date_hierarchy = 'started_at'
