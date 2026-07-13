"""
Beacon v0.4 — Core Models

Chapter 4 changes from Chapter 3:
- Cache invalidation continues from Chapter 3 (write-invalidate).
- The Page.save() method no longer sends synchronous notifications —
  that responsibility has moved to core/tasks.py and is called
  asynchronously from views.py after the save completes.
"""

import re

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Page(models.Model):
    """
    A single knowledge document in Beacon.

    Cache invalidation continues from Chapter 3.
    """

    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    body = models.TextField(
        blank=True,
        help_text="Plain text with optional [[wikilinks]] to other pages.",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["slug"], name="page_slug_idx"),
            models.Index(fields=["author", "-created_at"], name="page_author_created_idx"),
            models.Index(fields=["-updated_at"], name="page_updated_idx"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Write-invalidate (Chapter 3): delete cached page and page list entries.
        cache.delete(f"page:{self.slug}")
        self._invalidate_page_lists()

        self._rebuild_links()

    def delete(self, *args, **kwargs):
        slug = self.slug
        super().delete(*args, **kwargs)
        cache.delete(f"page:{slug}")
        self._invalidate_page_lists()

    def _invalidate_page_lists(self):
        """Delete all cached page list entries."""
        try:
            keys = cache.keys("page_list:*")
            if keys:
                cache.delete_many(keys)
        except Exception:
            pass

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
            if target.pk == self.pk:
                continue
            PageLink.objects.get_or_create(source=self, target=target)

    def get_absolute_url(self):
        return reverse("page_detail", kwargs={"slug": self.slug})

    def incoming_links(self):
        return Page.objects.filter(outgoing_links__target=self).distinct()

    def outgoing_pages(self):
        return Page.objects.filter(incoming_links__source=self).distinct()

    @property
    def link_count(self):
        return self.outgoing_links.count()


class PageLink(models.Model):
    """A directed edge in Beacon's knowledge graph."""

    source = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="outgoing_links"
    )
    target = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="incoming_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["source", "target"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source"], name="pagelink_source_idx"),
            models.Index(fields=["target"], name="pagelink_target_idx"),
        ]

    def __str__(self):
        return f"{self.source.title} → {self.target.title}"
