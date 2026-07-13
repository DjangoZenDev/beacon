"""Beacon v0.10 — WebSocket URL Routing."""
from django.urls import re_path
from .consumers import CollaborationConsumer
websocket_urlpatterns = [re_path(r"^page/(?P<slug>[-\w]+)/ws/$", CollaborationConsumer.as_asgi())]
