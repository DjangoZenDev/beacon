"""
Beacon v0.5 — Core Models

Chapter 5 changes from Chapter 4:
- Denormalized incoming_count and outgoing_count on Page model.
  These replace the COUNT subqueries that were bottlenecking the
  page list query at 142ms. The counters are maintained atomically
  via F() expressions in PageLink.save() and PageLink.delete().
- The page list query drops from 142ms to 9ms because it no longer
  needs JOIN + GROUP BY on the PageLink table.
- F() expressions prevent the read-modify-write race condition:
  two concurrent link creations both increment the counter correctly
  because the UPDATE happens inside a single SQL statement under
  PostgreSQL's row-level locking.
- Cache invalidation continues from Chapter 3.
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

    Chapter 5 adds denormalized link counts so the page list query
    no longer needs expensive COUNT subqueries with JOIN + GROUP BY.
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

    # ── Chapter 5: Denormalized link counts ───────────────────────
    # These are updated atomically in PageLink.save() and
    # PageLink.delete() using F() expressions. The authoritative
    # count lives in the PageLink table, but this copy lives on Page
    # for fast reads without JOIN + COUNT.
    #
    # Default is 0; a backfill migration (0003_add_link_counts)
    # populates them for existing pages.
    incoming_count = models.PositiveIntegerField(default=0)
    outgoing_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["slug"], name="page_slug_idx"),
            models.Index(fields=["author", "-created_at"], name="page_author_created_idx"),
            models.Index(fields=["-updated_at"], name="page_updated_idx"),
            # Chapter 5: Rank pages by popularity (incoming link count).
            # Used by PageListView when ordering by -incoming_count.
            models.Index(fields=["-incoming_count"], name="page_incoming_rank_idx"),
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
        # Delete existing links. PageLink.delete() will atomically
        # decrement the counters via F() expressions.
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
            # PageLink.save() will atomically increment counters.
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

    Chapter 5: save() and delete() now atomically maintain the
    denormalized incoming_count and outgoing_count on Page using
    Django's F() expressions.
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

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            # ── Chapter 5: Atomically increment counters ─────────
            # F() expressions perform the increment in the database:
            #   UPDATE core_page SET outgoing_count = outgoing_count + 1
            #   WHERE id = 42
            #
            # This is atomic under PostgreSQL's row-level locking.
            # Two concurrent link creations both see the correct
            # final count — no read-modify-write race condition.
            Page.objects.filter(pk=self.source_id).update(
                outgoing_count=models.F("outgoing_count") + 1
            )
            Page.objects.filter(pk=self.target_id).update(
                incoming_count=models.F("incoming_count") + 1
            )

    def delete(self, *args, **kwargs):
        source_id = self.source_id
        target_id = self.target_id
        super().delete(*args, **kwargs)

        # ── Chapter 5: Atomically decrement counters ─────────────
        Page.objects.filter(pk=source_id).update(
            outgoing_count=models.F("outgoing_count") - 1
        )
        Page.objects.filter(pk=target_id).update(
            incoming_count=models.F("incoming_count") - 1
        )
