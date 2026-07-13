"""
Beacon v0.12 — Core Models with Analytics Hooks.

Chapter 12 adds page view tracking and analytical event emission.
Every page view is recorded in ClickHouse for the analytical sidecar.
"""
import re
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

class Page(models.Model):
    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    body = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pages")
    organization_id = models.IntegerField(default=1, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        self._rebuild_links()
        if is_new:
            from .pageview_tracker import track_page_view
            track_page_view.delay(self.pk, "created")

    def _rebuild_links(self):
        PageLink.objects.filter(source=self).delete()
        wikilink_pattern = re.compile(r"\[\[([^\[\]]+?)\]\]")
        referenced_titles = wikilink_pattern.findall(self.body)
        for title in referenced_titles:
            title = title.strip()
            try:
                target = Page.objects.get(title__iexact=title)
            except Page.DoesNotExist:
                continue
            if target.pk == self.pk: continue
            PageLink.objects.get_or_create(source=self, target=target)

    def get_absolute_url(self):
        return reverse("page_detail", kwargs={"slug": self.slug})

    def incoming_links(self):
        return Page.objects.filter(outgoing_links__target=self).distinct()

    def outgoing_pages(self):
        return Page.objects.filter(incoming_links__source=self).distinct()

    @property
    def incoming_count(self):
        return self.incoming_links().count()

    @property
    def outgoing_count(self):
        return self.outgoing_pages().count()

class PageLink(models.Model):
    source = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="outgoing_links")
    target = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="incoming_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["source","target"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source.title} -> {self.target.title}"
