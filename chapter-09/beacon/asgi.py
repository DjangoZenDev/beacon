"""
Beacon v0.9 — ASGI Configuration for WebSocket Support.

Chapter 9 introduces Django Channels with Daphne as the ASGI server.
The ProtocolTypeRouter dispatches HTTP requests to the standard Django
WSGI handler and WebSocket connections to the AuthMiddlewareStack +
URLRouter for real-time collaboration.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "beacon.settings")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that requires it.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from core.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
