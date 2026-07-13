"""
Beacon v0.10 — Elasticsearch Integration (PageDocument)

Elasticsearch document mapping for Beacon pages. This is the
search-side representation of a Page, deliberately denormalized
to avoid database round-trips when rendering search results.

Index settings: 4 shards, 1 replica, 1s refresh interval.
"""

from elasticsearch_dsl import Document, Text, Date, Keyword, Integer
from elasticsearch_dsl.connections import connections
from django.conf import settings


# Establish the connection once, at import time.
connections.create_connection(
    hosts=settings.ELASTICSEARCH_HOSTS,
    timeout=30,
)


class PageDocument(Document):
    """
    Elasticsearch document mapping for a Beacon page.

    The title field has multi-fields for keyword (exact match)
    and suggest (autocomplete via ngram). The body is analyzed
    with the standard analyzer for full-text search.
    """

    title = Text(
        analyzer="standard",
        fields={
            "keyword": Keyword(),       # For exact-match queries.
            "suggest": Text(),          # For autocomplete (ngram).
        },
    )
    body = Text(analyzer="standard")
    slug = Keyword()
    author_username = Keyword()
    author_id = Integer()
    created_at = Date()
    updated_at = Date()
    link_count = Integer()

    class Index:
        name = "beacon_pages"
        settings = {
            "number_of_shards": 4,
            "number_of_replicas": 1,
            "refresh_interval": "1s",  # Near-real-time search.
        }

    @classmethod
    def from_page(cls, page):
        """
        Convert a Django Page model instance to an Elasticsearch document.

        Args:
            page: A core.models.Page instance.

        Returns:
            PageDocument ready for indexing.
        """
        return cls(
            meta={"id": page.pk},
            title=page.title,
            body=page.body,
            slug=page.slug,
            author_username=page.author.username,
            author_id=page.author.pk,
            created_at=page.created_at,
            updated_at=page.updated_at,
            link_count=page.outgoing_links.count(),
        )

    def to_search_result(self) -> dict:
        """
        Produce a lightweight dict for the search results page.

        Returns:
            Dict with id, title, slug, author, updated_at, and snippet.
        """
        return {
            "id": self.meta.id,
            "title": self.title,
            "slug": self.slug,
            "author": self.author_username,
            "updated_at": self.updated_at,
            "snippet": self._highlight_snippet(),
        }

    def _highlight_snippet(self, max_length: int = 200) -> str:
        """
        Extract a highlighted snippet from the body.

        If Elasticsearch highlight data is available (via meta.highlight),
        use it. Otherwise fall back to the first max_length characters.

        Args:
            max_length: Maximum snippet length in characters.

        Returns:
            Highlighted text snippet.
        """
        if hasattr(self.meta, "highlight") and self.meta.highlight:
            return "...".join(self.meta.highlight.body)[:max_length]
        return (
            self.body[:max_length] + "..."
            if len(self.body) > max_length
            else self.body
        )
