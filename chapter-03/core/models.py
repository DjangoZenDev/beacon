"""
Beacon v0.3 — Core Models

Chapter 3 changes from Chapter 2:
- Write-invalidate cache pattern: Page.save() and Page.delete() now
  call cache.delete() to invalidate cached page entries and page lists.
- Page._invalidate_page_lists() is deliberately blunt — it invalidates
  all cached page lists on any save. This is safe but wasteful. At
  Beacon's current scale (8,000 pages), it is acceptable. Chapter 6
  will introduce cache versioning for O(1) invalidation.
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

    Chapter 3 adds cache invalidation on save/delete.
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

        # ── Chapter 3: Write-invalidate cache ─────────────────
        # Delete this page's cache entry so the next read repopulates it
        # from PostgreSQL. This is the write-invalidate pattern:
        # safer than write-through because a cache update failure cannot
        # leave stale data.
        cache.delete(f"page:{self.slug}")

        # Invalidate all paginated page lists. A new or updated page
        # may change ordering and shift pages between paginated pages.
        # The blunt approach — delete all list caches — is safe and
        # acceptable at 8,000 pages. Chapter 6 introduces cache
        # versioning for O(1) invalidation.
        self._invalidate_page_lists()

        self._rebuild_links()

    def delete(self, *args, **kwargs):
        slug = self.slug
        super().delete(*args, **kwargs)
        cache.delete(f"page:{slug}")
        self._invalidate_page_lists()

    def _invalidate_page_lists(self):
        """Delete all cached page list entries.

        A blunt instrument, but safe. Incrementing a cache version
        number (see Chapter 6) is the production-grade alternative.
        """
        try:
            keys = cache.keys("page_list:*")
            if keys:
                cache.delete_many(keys)
        except Exception:
            # Cache operations should never prevent database writes.
            # If Redis is unreachable, the delete fails silently;
            # the stale cache entries will expire on their TTL.
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
    """
    A directed edge in Beacon's knowledge graph.

    Unchanged from Chapter 2.
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
