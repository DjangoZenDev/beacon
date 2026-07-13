"""
Beacon v0.7 — REST API URL Configuration

Chapter 7: DRF router exposes Page CRUD endpoints at /api/.
Used by external consumers (SPA frontend, mobile apps) and
service-to-service HTTP communication during the strangler
fig transition.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PageViewSet

router = DefaultRouter()
router.register(r"pages", PageViewSet, basename="page")

urlpatterns = [
    path("", include(router.urls)),
]
