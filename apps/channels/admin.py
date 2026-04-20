from django.contrib import admin
from .models import MessengerChannel, ChatSession, MessageLog


@admin.register(MessengerChannel)
class MessengerChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel_type', 'status', 'is_active', 'created_at')
    list_filter = ('channel_type', 'status', 'is_active')


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('external_user_name', 'channel', 'is_active', 'last_message_at')
    list_filter = ('is_active',)


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ('chat_session', 'direction', 'delivered', 'created_at')
    list_filter = ('direction', 'delivered')
