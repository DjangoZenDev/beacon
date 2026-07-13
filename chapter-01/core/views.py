"""
Beacon v0.1 — Views

Chapter 1 implements three class-based views:
- PageListView:  list all pages with optional full-text search
- PageDetailView: show a single page with its knowledge graph context
- PageEditView:  create and update pages

All views use Django's generic class-based views. No DRF yet — that
arrives in Chapter 7 when Beacon exposes a public API.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView

from .models import Page


class PageListView(LoginRequiredMixin, ListView):
    """
    List all pages, ten per page, with optional full-text search.

    Chapter 1 uses SQL LIKE for search. This is a deliberate trade-off:
    it works perfectly for up to ~10,000 pages and requires zero
    additional infrastructure. Chapter 10 replaces it with Elasticsearch
    when the knowledge graph grows too large for LIKE queries.
    """

    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 10

    def get_queryset(self):
        queryset = Page.objects.annotate(
            incoming_count=Count("incoming_links", distinct=True),
            outgoing_count=Count("outgoing_links", distinct=True),
        ).select_related("author")

        query = self.request.GET.get("q", "").strip()
        if query:
            # Chapter 1: simple LIKE-based search.
            # This scans the entire table on every query.
            # At 10,000 pages it will become slow.
            # Chapter 3 adds a GIN index; Chapter 10 adds Elasticsearch.
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

    The context includes:
    - incoming_links: pages that link to this page (backlinks)
    - outgoing_pages: pages this page links to
    - all context is queried efficiently with select_related
    """

    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_queryset(self):
        return Page.objects.select_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object

        # Fetch the knowledge graph neighborhood for this page.
        # Chapter 2 will optimize these queries with prefetch_related
        # when the N+1 problem becomes measurable.
        context["incoming_links"] = page.incoming_links().select_related("author")[:20]
        context["outgoing_pages"] = page.outgoing_pages().select_related("author")[:20]

        return context


class PageEditView(LoginRequiredMixin, UpdateView):
    """
    Create or update a page.

    Uses Django's UpdateView with the slug as the lookup. When no page
    with the given slug exists (for the 'new' slug), CreateView behavior
    is simulated by rendering an empty form.

    The wikilink parsing happens automatically in Page.save() — the view
    does not need to know about the knowledge graph.
    """

    model = Page
    template_name = "core/page_edit.html"
    fields = ["title", "body"]

    def get_object(self, queryset=None):
        """
        Return an existing Page or None for the 'new' URL.

        When the slug is 'new', return None so that get_form creates an
        empty form. The form_valid method will create a new Page.
        """
        slug = self.kwargs.get("slug")
        if slug == "new":
            return None
        return super().get_object(queryset)

    def form_valid(self, form):
        """Set the author and save."""
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
