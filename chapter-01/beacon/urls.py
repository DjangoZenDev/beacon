"""
Beacon v0.1 URL configuration.

Chapter 1 has exactly four URL patterns:
- /                  → page list + search
- /page/<slug>/      → page detail
- /page/<slug>/edit/ → edit page
- /admin/            → Django admin (for user management)
"""

from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.PageListView.as_view(), name="page_list"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page_detail"),
    path("page/<slug:slug>/edit/", views.PageEditView.as_view(), name="page_edit"),
]
