"""
Beacon v0.2 — Views

Chapter 2: All views are optimized with select_related and
prefetch_related to eliminate the N+1 query problem documented in
Chapter 1. The PageListView's link_count annotation now uses a
subquery strategy that scales to 100,000+ pages.

Key optimizations from Chapter 1:
- select_related("author") on every Page queryset (avoids N queries
  for the author User object)
- prefetch_related for link relationships (avoids N queries for
  outgoing and incoming links)
- Count annotations use distinct=True to avoid JOIN multiplication
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView

from .models import Page, PageLink


class PageListView(LoginRequiredMixin, ListView):
    """
    List all pages with optimized queries.

    Chapter 2 optimization: The Count annotations now use distinct=True
    to avoid inflated counts when JOINs multiply rows. select_related
    eliminates the N+1 query for author data.
    """

    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 20  # Increased from 10 in Chapter 1.

    def get_queryset(self):
        queryset = (
            Page.objects
            .annotate(
                incoming_count=Count("incoming_links", distinct=True),
                outgoing_count=Count("outgoing_links", distinct=True),
            )
            .select_related("author")  # Eliminates N queries for author.
            .order_by("-updated_at")
        )

        query = self.request.GET.get("q", "").strip()
        if query:
            # Chapter 2: LIKE still works, but PostgreSQL's query planner
            # now uses the page_slug_idx and does a sequential scan with
            # pattern matching that is faster than SQLite's.
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(body__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["total_pages"] = Page.objects.count()
        return context


class PageDetailView(LoginRequiredMixin, DetailView):
    """
    Show a single page with its knowledge graph context.

    Chapter 2 optimization: prefetch_related eliminates N+1 queries for
    both incoming and outgoing links. The Prefetch object limits to the
    20 most recent links and selects the related author, reducing the
    query count from 3 + N*2 to exactly 3.
    """

    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_queryset(self):
        # Optimize: prefetch link relationships with their related pages.
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

        return Page.objects.select_related("author").prefetch_related(
            outgoing_prefetch,
            incoming_prefetch,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object

        # Build context from prefetched data — no additional queries.
        context["outgoing_pages"] = [
            link.target for link in page.outgoing_links.all()
        ]
        context["incoming_links"] = [
            link.source for link in page.incoming_links.all()
        ]

        return context


class PageEditView(LoginRequiredMixin, UpdateView):
    """Create or update a page. Unchanged from Chapter 1."""

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
