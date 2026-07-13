"""
Beacon v0.6 — Core Models

Chapter 6 changes from Chapter 5:
- organization_id added to Page and PageLink for shard routing.
- unique_together for slug is now (organization_id, slug) — slugs are
  unique within an organization, not globally.
- Composite indexes include organization_id for shard-local queries.
- Denormalized link counts preserved from Chapter 5.
- Page.save() still rebuilds wikilinks and invalidates caches.
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

    Chapter 6 adds organization_id for shard routing. Every page belongs
    to exactly one organization, which is the shard key.
    """

    organization_id = models.IntegerField(
        db_index=True,
        help_text="The organization this page belongs to — used as the shard key.",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
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
    incoming_count = models.PositiveIntegerField(default=0)
    outgoing_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-updated_at"]
        # ── Chapter 6: unique_together is (organization_id, slug) ─
        unique_together = [["organization_id", "slug"]]
        indexes = [
            models.Index(fields=["organization_id", "slug"], name="page_org_slug_idx"),
            models.Index(fields=["organization_id", "-updated_at"], name="page_org_updated_idx"),
            models.Index(fields=["organization_id", "-incoming_count"], name="page_org_incoming_idx"),
            models.Index(fields=["author", "-created_at"], name="page_author_created_idx"),
        ]

    def __str__(self):
        return f"[org:{self.organization_id}] {self.title}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

        # Write-invalidate (Chapter 3): delete cached page and page list entries.
        cache.delete(f"page:{self.organization_id}:{self.slug}")
        self._invalidate_page_lists()

        self._rebuild_links()

    def delete(self, *args, **kwargs):
        slug = self.slug
        org_id = self.organization_id
        super().delete(*args, **kwargs)
        cache.delete(f"page:{org_id}:{slug}")
        self._invalidate_page_lists()

    def _invalidate_page_lists(self):
        """Delete all cached page list entries for this org."""
        try:
            keys = cache.keys(f"page_list:{self.organization_id}:*")
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
                target = Page.objects.get(
                    organization_id=self.organization_id,
                    title__iexact=title,
                )
            except Page.DoesNotExist:
                continue
            if target.pk == self.pk:
                continue
            PageLink.objects.get_or_create(source=self, target=target)

    def get_absolute_url(self):
        return reverse("page_detail", kwargs={"slug": self.slug})

    @property
    def link_count(self):
        return self.outgoing_links.count()


class PageLink(models.Model):
    """
    A directed edge in Beacon's knowledge graph.

    Chapter 6: organization_id added for shard routing. All links
    are within the same organization (cross-org links go through a
    separate global reference table managed by the application layer).
    """

    organization_id = models.IntegerField(
        db_index=True,
        help_text="Shard key — matches the source page's organization.",
    )
    source = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="outgoing_links"
    )
    target = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="incoming_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["source", "target"]]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "source"], name="pagelink_org_src_idx"),
            models.Index(fields=["organization_id", "target"], name="pagelink_org_tgt_idx"),
        ]

    def __str__(self):
        return f"[org:{self.organization_id}] {self.source.title} → {self.target.title}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and not self.organization_id:
            self.organization_id = self.source.organization_id
        super().save(*args, **kwargs)

        if is_new:
            # ── Chapter 5: Atomically increment counters ─────────
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
