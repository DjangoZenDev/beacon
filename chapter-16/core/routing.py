"""Beacon v0.16 — WebSocket Routing. Principle 9: CRDTs."""
from django.urls import re_path
from .consumers import CollaborationConsumer

websocket_urlpatterns = [
    re_path(r"^page/(?P<slug>[-\w]+)/ws/$", CollaborationConsumer.as_asgi()),
]
