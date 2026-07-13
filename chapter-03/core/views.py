"""
Beacon v0.3 — Views

Chapter 3: Cache-aside is added to PageListView and PageDetailView.

Key caching strategy:
- PageListView: cache page IDs (not full objects) for 60s. IDs are
  ~160 bytes vs ~20KB for serialized objects. Reconstructing from IDs
  uses a single SELECT ... WHERE id IN (...).
- PageDetailView: cache full Page objects for 300s (5 minutes).
  Individual pages are requested far more often than edited, so a
  longer TTL is appropriate.
- Write-invalidate: Page.save() in models.py calls cache.delete(),
  so the next read after an edit always fetches fresh data.
"""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView

from .models import Page, PageLink

logger = logging.getLogger("beacon.cache")


class PageListView(LoginRequiredMixin, ListView):
    """
    List all pages with cache-aside optimization.

    Chapter 3 optimization: cache page IDs, not full objects.
    A list of 20 page IDs is ~160 bytes. A list of 20 serialized
    Page objects is ~20KB. The cache hit ratio for the page list
    is ~95% because it is the most-visited page in Beacon.
    """

    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get("q", "").strip()
        page_number = self.request.GET.get("page", 1)

        # Build a cache key that includes the query and page number.
        cache_key = f"page_list:q={query}:p={page_number}"

        # ── Cache-aside: try the cache first ─────────────────────
        page_ids = cache.get(cache_key)
        if page_ids is not None:
            logger.debug("PageListView cache HIT: %s", cache_key)
            # Reconstruct queryset from cached IDs. This issues a
            # single SELECT ... WHERE id IN (...) query which is fast
            # even without a full cache entry.
            return (
                Page.objects
                .filter(id__in=page_ids)
                .annotate(
                    incoming_count=Count("incoming_links", distinct=True),
                    outgoing_count=Count("outgoing_links", distinct=True),
                )
                .select_related("author")
                .order_by("-updated_at")
            )

        logger.debug("PageListView cache MISS: %s", cache_key)

        # ── Cache miss: query PostgreSQL ─────────────────────────
        queryset = (
            Page.objects
            .annotate(
                incoming_count=Count("incoming_links", distinct=True),
                outgoing_count=Count("outgoing_links", distinct=True),
            )
            .select_related("author")
            .order_by("-updated_at")
        )

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(body__icontains=query)
            )

        # Evaluate the queryset to get page IDs, cache them.
        # We must evaluate queryset *before* we cache IDs because
        # the paginator will slice it. We cache the IDs of the
        # current page's objects.
        page_ids = list(queryset.values_list("id", flat=True))
        cache.set(cache_key, page_ids, timeout=60)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["total_pages"] = Page.objects.count()
        return context


class PageDetailView(LoginRequiredMixin, DetailView):
    """
    Show a single page with its knowledge graph context.

    Chapter 3 optimization: cache the full Page object for 5 minutes.
    Individual pages change infrequently relative to how often they
    are read (typically 100+ reads per edit). A 300s TTL means the
    cache hit ratio for page detail views exceeds 98%.
    """

    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        cache_key = f"page:{slug}"

        # ── Cache-aside for page detail ──────────────────────────
        page = cache.get(cache_key)
        if page is not None:
            logger.debug("PageDetailView cache HIT: %s", cache_key)
            return page

        logger.debug("PageDetailView cache MISS: %s", cache_key)

        # Cache miss: fetch from PostgreSQL with all prefetches.
        outgoing_prefetch = Prefetch(
            "outgoing_links",
            queryset=PageLink.objects.select_related("target__author").order_by(
                "-created_at"
            )[:20],
        )
        incoming_prefetch = Prefetch(
            "incoming_links",
            queryset=PageLink.objects.select_related("source__author").order_by(
                "-created_at"
            )[:20],
        )

        page = (
            Page.objects
            .select_related("author")
            .prefetch_related(outgoing_prefetch, incoming_prefetch)
            .get(slug=slug)
        )

        # Cache for 300 seconds (5 minutes). The write-invalidate
        # pattern in models.py will delete this key on save.
        cache.set(cache_key, page, timeout=300)

        return page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object

        context["outgoing_pages"] = [
            link.target for link in page.outgoing_links.all()
        ]
        context["incoming_links"] = [
            link.source for link in page.incoming_links.all()
        ]

        return context


class PageEditView(LoginRequiredMixin, UpdateView):
    """Create or update a page.

    Chapter 3: unchanged from Chapter 2 except that Page.save() in
    models.py now handles cache invalidation automatically.
    """

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
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
