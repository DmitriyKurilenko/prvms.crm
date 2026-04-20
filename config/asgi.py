import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from apps.core.channels_auth import JWTQueryAuthMiddleware
from .routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        'websocket': JWTQueryAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
