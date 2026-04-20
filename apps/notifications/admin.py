from django.contrib import admin
from .models import NotificationPreference, Notification, TelegramBinding


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('event', 'channel', 'is_enabled')
    list_filter = ('channel', 'is_enabled')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'event', 'channel', 'is_read', 'sent_at')
    list_filter = ('event', 'channel', 'is_read')
    search_fields = ('title', 'user__email')


@admin.register(TelegramBinding)
class TelegramBindingAdmin(admin.ModelAdmin):
    list_display = ('user', 'chat_id', 'username', 'is_active', 'linked_at')
