"""
Beacon v0.9 — WebSocket URL Routing.

Maps page-specific WebSocket connections to the CollaborationConsumer.
Route pattern: ws://host/page/<slug>/ws/
"""

from django.urls import re_path
from .consumers import CollaborationConsumer

websocket_urlpatterns = [
    re_path(r"^page/(?P<slug>[-\w]+)/ws/$", CollaborationConsumer.as_asgi()),
]
