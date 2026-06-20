# WebSocket routes will be added in later stages.
# Keeping this as a dedicated module makes it easy to extend without
# touching ASGI bootstrap.
from django.urls import path

from apps.ai_assistant.consumers import AIAssistantConsumer
from apps.channels.consumers import ChatConsumer
from apps.notifications.consumers import NotificationsConsumer

websocket_urlpatterns = [
    path('ws/notifications/', NotificationsConsumer.as_asgi()),
    path('ws/chat/', ChatConsumer.as_asgi()),
    path('ws/ai/', AIAssistantConsumer.as_asgi()),
]
