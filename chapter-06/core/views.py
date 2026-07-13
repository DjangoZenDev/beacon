"""
Beacon v0.6 — Views

Chapter 6 changes from Chapter 5:
- All querysets filter by organization_id from the request.
- OrganizationRequiredMixin enforces org-scoped access.
- PageDetailView uses (organization_id, slug) for lookup.
- PageEditView sets organization_id on new pages.
- Caching keys include organization_id for shard isolation.
"""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView

from .sharding.router import use_primary_for_request
from .models import Page, PageLink

logger = logging.getLogger("beacon.cache")


class OrganizationRequiredMixin:
    """
    Mixin that requires an organization context for all requests.

    Extracts organization_id from the request (via session, header,
    or URL parameter) and makes it available as self.organization_id.

    Without an organization context, shard routing is impossible —
    every request must be scoped to a specific organization.
    """

    organization_id = None

    def dispatch(self, request, *args, **kwargs):
        self.organization_id = self._get_organization_id(request)
        if self.organization_id is None:
            raise PermissionDenied(
                "Organization context is required. "
                "Set X-Beacon-Organization-Id header or log in via org selection."
            )
        return super().dispatch(request, *args, **kwargs)

    def _get_organization_id(self, request):
        """
        Resolve the organization_id for this request.

        Priority:
        1. X-Beacon-Organization-Id header (API clients)
        2. session['organization_id'] (web users)
        3. URL kwarg 'org_id' (explicit org URLs)
        """
        header = request.headers.get("X-Beacon-Organization-Id")
        if header:
            try:
                return int(header)
            except (TypeError, ValueError):
                pass

        session_org = request.session.get("organization_id")
        if session_org:
            return int(session_org)

        url_org = kwargs.get("org_id")
        if url_org:
            try:
                return int(url_org)
            except (TypeError, ValueError):
                pass

        return None


class PageListView(OrganizationRequiredMixin, LoginRequiredMixin, ListView):
    """
    List all pages in the current organization.

    Chapter 6: all querysets are scoped to the request's organization_id.
    The shard router uses organization_id to direct the query to the
    correct shard database.

    Denormalized counts and .only() optimization from Chapter 5 are
    preserved.
    """

    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 20

    def get_queryset(self):
        org_id = self.organization_id
        query = self.request.GET.get("q", "").strip()
        page_number = self.request.GET.get("page", 1)

        cache_key = f"page_list:{org_id}:q={query}:p={page_number}"

        page_ids = cache.get(cache_key)
        if page_ids is not None:
            logger.debug("PageListView cache HIT: %s", cache_key)
            return (
                Page.objects
                .filter(organization_id=org_id, id__in=page_ids)
                .select_related("author")
                .only(
                    "title", "slug", "author",
                    "updated_at", "incoming_count", "outgoing_count",
                )
                .order_by("-incoming_count", "-updated_at")
            )

        logger.debug("PageListView cache MISS: %s", cache_key)

        queryset = (
            Page.objects
            .filter(organization_id=org_id)
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
        context["total_pages"] = Page.objects.filter(
            organization_id=self.organization_id
        ).count()
        context["organization_id"] = self.organization_id
        return context


class PageDetailView(OrganizationRequiredMixin, LoginRequiredMixin, DetailView):
    """
    Show a single page with its knowledge graph context.

    Chapter 6: lookup uses (organization_id, slug) since slugs are
    unique only within an organization.
    """

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

        context["outgoing_pages"] = [
            link.target for link in page.outgoing_links.all()
        ]
        context["incoming_links"] = [
            link.source for link in page.incoming_links.all()
        ]
        context["organization_id"] = self.organization_id

        try:
            from .external import get_related_articles
            context["related_articles"] = get_related_articles(page.title)
        except Exception:
            context["related_articles"] = []

        return context


class PageEditView(OrganizationRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    Create or update a page scoped to the current organization.

    Chapter 6: organization_id is set automatically on new pages.
    The user never chooses a shard — the system routes by org.
    """

    model = Page
    template_name = "core/page_edit.html"
    fields = ["title", "body"]

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        if slug == "new":
            return None
        return (
            super()
            .get_object(queryset)
            .filter(organization_id=self.organization_id)
            .get(slug=slug)
        )

    def form_valid(self, form):
        if form.instance.pk is None:
            form.instance.organization_id = self.organization_id
        form.instance.author = self.request.user
        response = super().form_valid(form)

        # ── Chapter 5: Force primary for read-after-write ────────
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
        base = reverse_lazy("page_detail", kwargs={"slug": self.object.slug})
        return f"{base}?from=edit"
