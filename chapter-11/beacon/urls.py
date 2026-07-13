"""Beacon v0.11 URL configuration."""

from django.contrib import admin
from django.urls import path, include
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.PageListView.as_view(), name="page_list"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page_detail"),
    path("page/<slug:slug>/edit/", views.PageEditView.as_view(), name="page_edit"),
    path("search/", views.PageSearchView.as_view(), name="search"),
    path("feed/", views.FeedView.as_view(), name="feed"),
    path("api/", include("core.api_urls")),
]
