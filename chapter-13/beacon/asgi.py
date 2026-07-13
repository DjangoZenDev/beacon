"""
Beacon v0.13 — ASGI Configuration for WebSocket Support.

Chapter 9 introduced Django Channels with Daphne as the ASGI server.
Carried forward to Chapter 13: Multi-Region / Kubernetes.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "beacon.settings")

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
