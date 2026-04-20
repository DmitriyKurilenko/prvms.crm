from django.contrib import admin
from .models import SIPTrunk, PhoneExtension, IVRMenu, CallQueue, CallRecord


@admin.register(SIPTrunk)
class SIPTrunkAdmin(admin.ModelAdmin):
    list_display = ('name', 'trunk_type', 'status', 'is_active', 'created_at')
    list_filter = ('trunk_type', 'status', 'is_active')


@admin.register(PhoneExtension)
class PhoneExtensionAdmin(admin.ModelAdmin):
    list_display = ('extension', 'manager', 'webrtc_enabled', 'is_active')
    list_filter = ('is_active', 'webrtc_enabled')


@admin.register(IVRMenu)
class IVRMenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'timeout', 'is_active')


@admin.register(CallQueue)
class CallQueueAdmin(admin.ModelAdmin):
    list_display = ('name', 'strategy', 'ring_timeout', 'is_active')
    list_filter = ('strategy', 'is_active')


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = ('direction', 'caller_number', 'called_number', 'result', 'duration', 'started_at')
    list_filter = ('direction', 'result')
    date_hierarchy = 'started_at'
