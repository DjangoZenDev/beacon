
"""
Beacon v0.7 — Views with DRF support.

Chapter 7 adds PageViewSet for REST API endpoints alongside the
existing template views from Chapter 6.
"""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView
from rest_framework import viewsets, permissions, filters
from rest_framework.pagination import PageNumberPagination

from .db_router import use_primary_for_request
from .models import Page, PageLink
from .serializers import PageSerializer, PageListSerializer

logger = logging.getLogger("beacon.cache")


class OrganizationRequiredMixin:
    """Mixin that extracts organization_id from the request.

    In production, this would decode a JWT or session claim.
    For the companion repo, we use a query parameter and
    default to org 1 for backward compatibility.
    """

    @property
    def organization_id(self):
        org_id = self.request.GET.get("org_id")
        if org_id:
            return int(org_id)
        if hasattr(self.request, "user") and hasattr(self.request.user, "organization_id"):
            return self.request.user.organization_id
        return 1  # Default org for companion repo


class PageListView(OrganizationRequiredMixin, LoginRequiredMixin, ListView):
    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get("q", "").strip()
        page_number = self.request.GET.get("page", 1)
        org_id = self.organization_id

        cache_key = f"page_list:{org_id}:q={query}:p={page_number}"

        page_ids = cache.get(cache_key)
        if page_ids is not None:
            return (
                Page.objects
                .filter(id__in=page_ids, organization_id=org_id)
                .select_related("author")
                .only("title", "slug", "author", "organization_id",
                       "updated_at", "incoming_count", "outgoing_count")
                .order_by("-incoming_count", "-updated_at")
            )

        queryset = (
            Page.objects
            .filter(organization_id=org_id)
            .select_related("author")
            .only("title", "slug", "author", "organization_id",
                   "updated_at", "incoming_count", "outgoing_count")
            .order_by("-incoming_count", "-updated_at")
        )

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(body__icontains=query)
            )

        page_ids = list(queryset.values_list("id", flat=True))
        cache.set(cache_key, page_ids, timeout=60)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["total_pages"] = Page.objects.filter(
            organization_id=self.organization_id
        ).count()
        return context


class PageDetailView(OrganizationRequiredMixin, LoginRequiredMixin, DetailView):
    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        org_id = self.organization_id
        cache_key = f"page:{org_id}:{slug}"

        from_edit = self.request.GET.get("from") == "edit"
        if from_edit:
            use_primary_for_request()
            cache.delete(cache_key)

        page = cache.get(cache_key)
        if page is not None and not from_edit:
            return page

        outgoing_prefetch = Prefetch(
            "outgoing_links",
            queryset=PageLink.objects.select_related("target__author")
            .order_by("-created_at")[:20],
        )
        incoming_prefetch = Prefetch(
            "incoming_links",
            queryset=PageLink.objects.select_related("source__author")
            .order_by("-created_at")[:20],
        )

        page = (
            Page.objects
            .filter(organization_id=org_id)
            .select_related("author")
            .prefetch_related(outgoing_prefetch, incoming_prefetch)
            .get(slug=slug)
        )

        cache.set(cache_key, page, timeout=300)
        return page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object
        context["outgoing_pages"] = [link.target for link in page.outgoing_links.all()]
        context["incoming_links"] = [link.source for link in page.incoming_links.all()]
        try:
            from .external import get_related_articles
            context["related_articles"] = get_related_articles(page.title)
        except Exception:
            context["related_articles"] = []
        return context


class PageEditView(OrganizationRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Page
    template_name = "core/page_edit.html"
    fields = ["title", "body"]

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        if slug == "new":
            return None
        return super().get_object(queryset)

    def form_valid(self, form):
        form.instance.author = self.request.user
        if not form.instance.organization_id:
            form.instance.organization_id = self.organization_id
        response = super().form_valid(form)
        use_primary_for_request()
        try:
            from .tasks import notify_bookmarkers
            notify_bookmarkers.delay(
                page_id=self.object.pk,
                edited_by_user_id=self.request.user.pk,
            )
        except Exception as exc:
            logger.warning("Failed to enqueue notify_bookmarkers: %s", exc)
        return response

    def get_success_url(self):
        base = reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
        return f"{base}?from=edit"


# ── Chapter 7: DRF ViewSet ────────────────────────────────────

class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class PageViewSet(viewsets.ModelViewSet):
    queryset = Page.objects.all().select_related("author")
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body"]
    ordering_fields = ["updated_at", "incoming_count", "created_at"]
    ordering = ["-updated_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return PageListSerializer
        return PageSerializer

    def get_queryset(self):
        org_id = self.request.query_params.get("organization_id")
        qs = super().get_queryset()
        if org_id:
            qs = qs.filter(organization_id=int(org_id))
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
