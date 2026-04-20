# WebSocket routes will be added in later stages.
# Keeping this as a dedicated module makes it easy to extend without
# touching ASGI bootstrap.
from django.urls import path

from apps.notifications.consumers import NotificationsConsumer
from apps.channels.consumers import ChatConsumer

websocket_urlpatterns = [
    path('ws/notifications/', NotificationsConsumer.as_asgi()),
    path('ws/chat/', ChatConsumer.as_asgi()),
]
