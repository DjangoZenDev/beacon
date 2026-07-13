
"""
Beacon v0.11 — Views. Template views + DRF ViewSet + Elasticsearch search + FeedView.

Chapter 11 adds FeedView: hybrid fan-out feed for authenticated users.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, TemplateView, View
from django.views.generic.edit import UpdateView
from rest_framework import viewsets, permissions, filters, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from .sharding.router import use_primary_for_request
from .models import Page, PageLink
from .serializers import PageSerializer, PageListSerializer

logger = logging.getLogger("beacon.cache")


class OrganizationRequiredMixin:
    @property
    def organization_id(self):
        org_id = self.request.GET.get("org_id")
        if org_id: return int(org_id)
        if hasattr(self.request, "user") and hasattr(self.request.user, "organization_id"):
            return self.request.user.organization_id
        return 1


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
            return Page.objects.filter(id__in=page_ids, organization_id=org_id).select_related("author").only("title","slug","author","organization_id","updated_at","incoming_count","outgoing_count").order_by("-incoming_count","-updated_at")
        qs = Page.objects.filter(organization_id=org_id).select_related("author").only("title","slug","author","organization_id","updated_at","incoming_count","outgoing_count").order_by("-incoming_count","-updated_at")
        if query: qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
        page_ids = list(qs.values_list("id", flat=True))
        cache.set(cache_key, page_ids, timeout=60)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        ctx["total_pages"] = Page.objects.filter(organization_id=self.organization_id).count()
        return ctx


class PageDetailView(OrganizationRequiredMixin, LoginRequiredMixin, DetailView):
    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        org_id = self.organization_id
        cache_key = f"page:{org_id}:{slug}"
        from_edit = self.request.GET.get("from") == "edit"
        if from_edit: use_primary_for_request(); cache.delete(cache_key)
        page = cache.get(cache_key)
        if page is not None and not from_edit: return page
        op = Prefetch("outgoing_links", queryset=PageLink.objects.select_related("target__author").order_by("-created_at")[:20])
        ip = Prefetch("incoming_links", queryset=PageLink.objects.select_related("source__author").order_by("-created_at")[:20])
        page = Page.objects.filter(organization_id=org_id).select_related("author").prefetch_related(op, ip).get(slug=slug)
        cache.set(cache_key, page, timeout=300)
        return page

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object
        ctx["outgoing_pages"] = [l.target for l in page.outgoing_links.all()]
        ctx["incoming_links"] = [l.source for l in page.incoming_links.all()]
        try:
            from .external import get_related_articles
            ctx["related_articles"] = get_related_articles(page.title)
        except Exception: ctx["related_articles"] = []
        return ctx


class PageEditView(OrganizationRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Page
    template_name = "core/page_edit.html"
    fields = ["title", "body"]

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        if slug == "new": return None
        return super().get_object(queryset)

    def form_valid(self, form):
        form.instance.author = self.request.user
        if not form.instance.organization_id: form.instance.organization_id = self.organization_id
        response = super().form_valid(form)
        use_primary_for_request()
        try:
            from .tasks import notify_bookmarkers
            import uuid
            notify_bookmarkers.delay(page_id=self.object.pk, edited_by_user_id=self.request.user.pk, idempotency_key=f"notify:{self.object.pk}:{self.request.user.pk}:{uuid.uuid4().hex[:12]}")
        except Exception as exc: logger.warning("Failed to enqueue notify: %s", exc)
        # Ch11: Create a feed Event for the edit.
        try:
            from .models import Event
            Event.objects.create(page=self.object, event_type="page.updated", actor=self.request.user, metadata={"source": "page_edit"})
        except Exception: pass
        return response

    def get_success_url(self):
        base = reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
        return f"{base}?from=edit"


# ── Chapter 10: Elasticsearch Search View ─────────────────

class PageSearchView(OrganizationRequiredMixin, LoginRequiredMixin, TemplateView):
    """
    Elasticsearch-backed search using multi_match with BM25 scoring.

    Fields: title^3 (3× boost), body (1×), fuzziness=AUTO.
    Faceted aggregations by author.
    """
    template_name = "core/search_results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        ctx["query"] = query

        if not query:
            ctx["results"] = []
            ctx["total"] = 0
            ctx["facets"] = {}
            return ctx

        try:
            from elasticsearch_dsl import Search, Q as ESQ
            from core.search import PageDocument

            s = Search(index="beacon_pages").query(
                "multi_match",
                query=query,
                fields=["title^3", "body"],
                fuzziness="AUTO",
            )
            s.aggs.bucket("by_author", "terms", field="author_username", size=10)
            s = s[:50]
            s = s.highlight("body", fragment_size=150, number_of_fragments=1)

            response = s.execute()

            results = []
            for hit in response:
                results.append({
                    "id": hit.meta.id,
                    "title": hit.title,
                    "slug": hit.slug,
                    "author": hit.author_username,
                    "updated_at": hit.updated_at,
                    "snippet": (
                        "...".join(hit.meta.highlight.body)[:200]
                        if hasattr(hit.meta, "highlight") and hit.meta.highlight
                        else (hit.body[:200] + "..." if len(hit.body) > 200 else hit.body)
                    ),
                })

            facets = {}
            if hasattr(response, "aggregations") and response.aggregations:
                facets["by_author"] = [
                    {"author": b.key, "count": b.doc_count}
                    for b in response.aggregations.by_author.buckets
                ]

            ctx["results"] = results
            ctx["total"] = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total
            ctx["facets"] = facets

        except Exception as exc:
            logger.warning("Elasticsearch search failed: %s", exc)
            # Fall back to ILIKE search.
            qs = Page.objects.filter(
                Q(title__icontains=query) | Q(body__icontains=query)
            ).select_related("author").only(
                "title", "slug", "author", "body", "updated_at"
            ).order_by("-incoming_count", "-updated_at")[:50]

            ctx["results"] = [{
                "id": p.pk,
                "title": p.title,
                "slug": p.slug,
                "author": p.author.username,
                "updated_at": p.updated_at,
                "snippet": (p.body[:200] + "..." if len(p.body) > 200 else p.body),
            } for p in qs]
            ctx["total"] = len(ctx["results"])
            ctx["facets"] = {}

        return ctx


# ── Chapter 11: Activity Feed View ─────────────────────────

class FeedView(LoginRequiredMixin, TemplateView):
    """
    Activity feed for the authenticated user.

    Uses the hybrid FeedManager: Redis sorted set (fan-out on write)
    merged with celebrity page events (fan-out on read).
    """
    template_name = "core/feed.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        try:
            from .feed import feed_manager
            feed_items = feed_manager.get_user_feed(self.request.user, limit=50)
        except Exception as exc:
            logger.warning("Feed retrieval failed: %s", exc)
            feed_items = []

        ctx["feed_items"] = feed_items
        ctx["feed_count"] = len(feed_items)
        return ctx


# ── DRF ViewSet ────────────────────────────────────────────

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
        return PageListSerializer if self.action == "list" else PageSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        org_id = self.request.query_params.get("organization_id")
        if org_id: qs = qs.filter(organization_id=int(org_id))
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
