"""Beacon v0.7 URL configuration."""
from django.contrib import admin
from django.urls import path, include
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.PageListView.as_view(), name="page_list"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page_detail"),
    path("page/<slug:slug>/edit/", views.PageEditView.as_view(), name="page_edit"),
    # ── Chapter 7: REST API endpoints ───────────────────────────
    path("api/", include("core.api_urls")),
]
