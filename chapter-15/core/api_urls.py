from django.urls import path
from . import views

urlpatterns = [
    path("pages/", views.PageListAPI.as_view(), name="api_page_list"),
    path("pages/<slug:slug>/", views.PageDetailAPI.as_view(), name="api_page_detail"),
]
