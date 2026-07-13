"""
Beacon v0.5 — Views

Chapter 5 changes from Chapter 4:
- PageListView.get_queryset uses .only() to skip loading the body
  field (saves 95% of data transferred for the list view).
- PageListView no longer uses Count() subqueries — denormalized
  incoming_count/outgoing_count columns are read directly.
- PageListView orders by -incoming_count (popularity rank).
- PageDetailView calls use_primary_for_request() after save to
  ensure reads within the same request see the latest data.
- PageEditView.form_valid calls use_primary_for_request() after
  saving so the redirect reads from the primary.
"""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView

from .db_router import use_primary_for_request
from .models import Page, PageLink

logger = logging.getLogger("beacon.cache")


class PageListView(LoginRequiredMixin, ListView):
    """
    List all pages with denormalized counts and .only() optimization.

    Chapter 5 optimization:
    - Denormalized incoming_count/outgoing_count columns replace
      Count() subqueries. The query is a simple SELECT with no JOINs,
      no GROUP BY. Query time dropped from 142ms to 9ms.
    - .only() fetches only the columns the template needs, skipping
      the body field (which can be tens of KB). For 20 pages, this
      saves ~95% of the data transferred from PostgreSQL.
    - Ordering by -incoming_count surfaces popular pages first.
    - Reads go to the replica (via ReadReplicaRouter) since the page
      list tolerates slight staleness.
    """

    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get("q", "").strip()
        page_number = self.request.GET.get("page", 1)

        cache_key = f"page_list:q={query}:p={page_number}"

        page_ids = cache.get(cache_key)
        if page_ids is not None:
            logger.debug("PageListView cache HIT: %s", cache_key)
            return (
                Page.objects
                .filter(id__in=page_ids)
                .select_related("author")
                # ── Chapter 5: .only() to skip body field ────────
                .only(
                    "title", "slug", "author",
                    "updated_at", "incoming_count", "outgoing_count",
                )
                .order_by("-incoming_count", "-updated_at")
            )

        logger.debug("PageListView cache MISS: %s", cache_key)

        # ── Chapter 5: No more Count subqueries! ─────────────────
        # Denormalized counts are read directly from the Page row.
        queryset = (
            Page.objects
            .select_related("author")
            .only(
                "title", "slug", "author",
                "updated_at", "incoming_count", "outgoing_count",
            )
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
        context["total_pages"] = Page.objects.count()
        return context


class PageDetailView(LoginRequiredMixin, DetailView):
    """
    Show a single page with its knowledge graph context.

    Chapter 5: uses use_primary_for_request() when coming from an
    edit to ensure the user sees their changes immediately (no
    replication lag on read-after-write).
    """

    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        cache_key = f"page:{slug}"

        # If we came from an edit, reads must go to the primary.
        # The view checks the referer or a query parameter set by
        # PageEditView.get_success_url.
        from_edit = self.request.GET.get("from") == "edit"
        if from_edit:
            use_primary_for_request()
            # Bypass cache on edit redirect — the cache may still
            # have the old version.
            cache.delete(cache_key)

        page = cache.get(cache_key)
        if page is not None and not from_edit:
            logger.debug("PageDetailView cache HIT: %s", cache_key)
            return page

        logger.debug("PageDetailView cache MISS: %s", cache_key)

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

        try:
            from .external import get_related_articles
            context["related_articles"] = get_related_articles(page.title)
        except Exception:
            context["related_articles"] = []

        return context


class PageEditView(LoginRequiredMixin, UpdateView):
    """
    Create or update a page.

    Chapter 5: form_valid now calls use_primary_for_request() after
    saving so the subsequent redirect (to PageDetailView) reads from
    the primary instead of the replica. Without this, the user might
    see a stale version due to replication lag.
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
        response = super().form_valid(form)

        # ── Chapter 5: Force primary for read-after-write ────────
        # After saving, the redirect to PageDetailView must read from
        # the primary because the replica may not have received the
        # write yet (10-100ms replication lag).
        use_primary_for_request()

        # Chapter 4: send notifications in the background.
        try:
            from .tasks import notify_bookmarkers
            notify_bookmarkers.delay(
                page_id=self.object.pk,
                edited_by_user_id=self.request.user.pk,
            )
        except Exception as exc:
            logger.warning(
                "Failed to enqueue notify_bookmarkers for page %s: %s",
                self.object.pk, exc,
            )

        return response

    def get_success_url(self):
        # Add ?from=edit so PageDetailView knows to use the primary
        # and bypass the cache.
        base = reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
        return f"{base}?from=edit"
