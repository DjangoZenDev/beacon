"""
Beacon v0.15 — Views with CDN Support.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView
from rest_framework import generics
from .models import Page
from .serializers import PageSerializer

class PageListView(LoginRequiredMixin, ListView):
    model = Page; template_name = "core/page_list.html"; context_object_name = "pages"; paginate_by = 10
    def get_queryset(self):
        qs = Page.objects.annotate(incoming_count=Count("incoming_links",distinct=True),outgoing_count=Count("outgoing_links",distinct=True)).select_related("author")
        query = self.request.GET.get("q","").strip()
        if query: qs = qs.filter(Q(title__icontains=query)|Q(body__icontains=query))
        return qs
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q","")
        ctx["total_pages"] = Page.objects.count()
        return ctx

class PageDetailView(LoginRequiredMixin, DetailView):
    model = Page; template_name = "core/page_detail.html"; context_object_name = "page"
    def get_queryset(self): return Page.objects.select_related("author")
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object
        ctx["incoming_links"] = page.incoming_links().select_related("author")[:20]
        ctx["outgoing_pages"] = page.outgoing_pages().select_related("author")[:20]
        ctx["incoming_count"] = page.incoming_count
        ctx["outgoing_count"] = page.outgoing_count
        return ctx

class PageEditView(LoginRequiredMixin, UpdateView):
    model = Page; template_name = "core/page_edit.html"; fields = ["title","body"]
    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        if slug == "new": return None
        return super().get_object(queryset)
    def form_valid(self, form):
        form.instance.author = self.request.user
        resp = super().form_valid(form)
        from .tasks import invalidate_cdn_cache
        invalidate_cdn_cache.delay(self.object.slug)
        return resp
    def get_success_url(self):
        return reverse_lazy("page_detail", kwargs={"slug": self.object.slug})

class PageListAPI(generics.ListCreateAPIView):
    queryset = Page.objects.all(); serializer_class = PageSerializer

class PageDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Page.objects.all(); serializer_class = PageSerializer; lookup_field = "slug"
