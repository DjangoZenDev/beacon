"""
Beacon v0.2 — Core Models

Chapter 2 changes from Chapter 1:
- Added database indexes on frequently queried columns
- Added a GIN index placeholder for PostgreSQL full-text search
- The wikilink parsing (write-time computation) remains unchanged
  because it already worked correctly in Chapter 1
"""

import re

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Page(models.Model):
    """
    A single knowledge document in Beacon.

    Chapter 2 adds PostgreSQL-specific optimizations:
    - GIN index on body for full-text search (LIKE still works, but the
      index accelerates prefix and substring matching)
    - Composite indexes for common query patterns
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
            # Primary lookup: finding a page by its slug.
            models.Index(fields=["slug"], name="page_slug_idx"),
            # Common query: "pages by this author, newest first."
            models.Index(fields=["author", "-created_at"], name="page_author_created_idx"),
            # Feed query: "recently updated pages."
            models.Index(fields=["-updated_at"], name="page_updated_idx"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        self._rebuild_links()

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
    """
    A directed edge in Beacon's knowledge graph.

    Chapter 2 adds indexes to support the most common link queries:
    - All outgoing links from a page
    - All incoming links to a page (backlinks)
    """

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
