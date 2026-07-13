"""
Beacon v0.4 — Views

Chapter 4 changes from Chapter 3:
- PageEditView.form_valid now calls notify_bookmarkers.delay() after
  saving, moving notification delivery off the critical path.
- PageDetailView.get_context_data optionally includes related articles
  from the external API (via core/external.py).
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

    Cache-aside from Chapter 3: cache page IDs for 60s.
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
                .annotate(
                    incoming_count=Count("incoming_links", distinct=True),
                    outgoing_count=Count("outgoing_links", distinct=True),
                )
                .select_related("author")
                .order_by("-updated_at")
            )

        logger.debug("PageListView cache MISS: %s", cache_key)

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

    Chapter 4: optionally fetches related articles from the external
    API (with caching and a 200ms timeout). The sidebar gracefully
    handles an empty result — it simply does not render the related
    articles section.
    """

    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        cache_key = f"page:{slug}"

        page = cache.get(cache_key)
        if page is not None:
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

        # ── Chapter 4: Related articles from external API ─────────
        # The external function is cached with a 15-minute TTL and
        # has a 200ms timeout. If the API is slow or unreachable, we
        # get an empty list and the sidebar omits the section.
        try:
            from .external import get_related_articles
            context["related_articles"] = get_related_articles(page.title)
        except Exception:
            context["related_articles"] = []

        return context


class PageEditView(LoginRequiredMixin, UpdateView):
    """
    Create or update a page.

    Chapter 4: form_valid now calls notify_bookmarkers.delay() after
    saving to move notification delivery off the critical path. The
    user sees the success page immediately; notifications are sent
    asynchronously by the Celery worker.
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

        # ── Chapter 4: Fire-and-forget notification task ──────────
        # .delay() serializes the arguments to JSON, pushes them onto
        # the Redis queue, and returns immediately (~1ms). The Celery
        # worker picks up the task whenever it is ready.
        #
        # The try/except is critical: if Redis is down, .delay() raises
        # ConnectionError. We catch it and log — the page save succeeds
        # regardless. Notifications are best-effort.
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
        return reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
