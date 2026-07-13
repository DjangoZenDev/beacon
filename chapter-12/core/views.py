"""
Beacon v0.12 — Views with Analytics Integration.
Chapter 12: Every page view emits an analytics event to ClickHouse.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView
from rest_framework import generics
from .models import Page
from .serializers import PageSerializer

class PageListView(LoginRequiredMixin, ListView):
    model = Page
    template_name = "core/page_list.html"
    context_object_name = "pages"
    paginate_by = 10

    def get_queryset(self):
        queryset = Page.objects.annotate(incoming_count=Count("incoming_links",distinct=True),outgoing_count=Count("outgoing_links",distinct=True)).select_related("author")
        query = self.request.GET.get("q","").strip()
        if query:
            queryset = queryset.filter(Q(title__icontains=query)|Q(body__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q","")
        context["total_pages"] = Page.objects.count()
        return context

class PageDetailView(LoginRequiredMixin, DetailView):
    model = Page
    template_name = "core/page_detail.html"
    context_object_name = "page"

    def get_queryset(self):
        return Page.objects.select_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object
        context["incoming_links"] = page.incoming_links().select_related("author")[:20]
        context["outgoing_pages"] = page.outgoing_pages().select_related("author")[:20]
        context["incoming_count"] = page.incoming_count
        context["outgoing_count"] = page.outgoing_count
        # Track view in ClickHouse via Celery
        from .pageview_tracker import track_page_view
        track_page_view.delay(page.pk, "viewed")
        return context

class PageEditView(LoginRequiredMixin, UpdateView):
    model = Page
    template_name = "core/page_edit.html"
    fields = ["title","body"]

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        if slug == "new": return None
        return super().get_object(queryset)

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("page_detail", kwargs={"slug": self.object.slug})

class PageListAPI(generics.ListCreateAPIView):
    queryset = Page.objects.all()
    serializer_class = PageSerializer

class PageDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    lookup_field = "slug"
