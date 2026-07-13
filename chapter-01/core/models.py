"""
Beacon v0.1 — Core Models

Chapter 1 introduces two models:
- Page: a knowledge document with title, slug, body, author, timestamps
- PageLink: a structured relationship between two pages

The PageLink model encodes Beacon's core insight: knowledge is a graph,
not a folder hierarchy. Every wikilink in a page body is parsed at save
time and stored as a row in PageLink so that backlinks and relationships
are queryable without scanning page bodies at read time.

This is the first instance of *write-time computation* — a pattern that
will reappear throughout the book in caching, materialized views, and
event sourcing. Do the work once, when data is created, so that reads
stay fast.
"""

import re

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Page(models.Model):
    """
    A single knowledge document in Beacon.

    Every page is both a human-readable document and a structured,
    queryable node in the knowledge graph. The `body` field uses plain
    text with wikilink syntax ([[Page Title]]) that is parsed on save.
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

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Auto-generate slug from title if not provided.
        if not self.slug:
            self.slug = slugify(self.title)

        # Save the page first so it has a primary key.
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Parse wikilinks and update the PageLink table.
        # This is write-time computation: we do the parsing once, on save,
        # so that every read of the knowledge graph is a cheap query.
        self._rebuild_links()

    def _rebuild_links(self):
        """Parse [[wikilinks]] from body and sync the PageLink table."""
        # Remove existing outgoing links for this page.
        PageLink.objects.filter(source=self).delete()

        # Find all [[Page Title]] patterns in the body.
        wikilink_pattern = re.compile(r"\[\[([^\[\]]+?)\]\]")
        referenced_titles = wikilink_pattern.findall(self.body)

        for title in referenced_titles:
            title = title.strip()
            # Try to find the target page by title (case-insensitive).
            try:
                target = Page.objects.get(title__iexact=title)
            except Page.DoesNotExist:
                # Link to a page that does not exist yet.
                # Chapter 10 will turn these into "wanted pages."
                continue

            # Avoid self-links.
            if target.pk == self.pk:
                continue

            PageLink.objects.get_or_create(
                source=self,
                target=target,
            )

    def get_absolute_url(self):
        return reverse("page_detail", kwargs={"slug": self.slug})

    def incoming_links(self):
        """Return all pages that link to this page."""
        return Page.objects.filter(outgoing_links__target=self).distinct()

    def outgoing_pages(self):
        """Return all pages this page links to."""
        return Page.objects.filter(incoming_links__source=self).distinct()

    @property
    def link_count(self):
        """Number of outgoing links from this page."""
        return self.outgoing_links.count()


class PageLink(models.Model):
    """
    A directed edge in Beacon's knowledge graph.

    source → target means that `source` contains a [[wikilink]] to `target`.
    This table enables backlink queries, graph visualization, and
    relationship-based search — all without scanning page bodies.
    """

    source = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="outgoing_links",
    )
    target = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="incoming_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["source", "target"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source.title} → {self.target.title}"
