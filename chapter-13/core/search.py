
"""
Beacon v0.13 — Elasticsearch Integration (PageDocument)

Chapter 13: Search continues to work per-region with local Elasticsearch
clusters. Multi-region search federation is handled at the Istio layer.
Carried forward from Chapter 10.
"""

from elasticsearch_dsl import Document, Text, Date, Keyword, Integer
from elasticsearch_dsl.connections import connections
from django.conf import settings

connections.create_connection(hosts=settings.ELASTICSEARCH_HOSTS, timeout=30)


class PageDocument(Document):
    """Elasticsearch document mapping for a Beacon page."""

    title = Text(analyzer="standard", fields={"keyword": Keyword(), "suggest": Text()})
    body = Text(analyzer="standard")
    slug = Keyword()
    author_username = Keyword()
    author_id = Integer()
    created_at = Date()
    updated_at = Date()
    link_count = Integer()

    class Index:
        name = "beacon_pages"
        settings = {"number_of_shards": 4, "number_of_replicas": 1, "refresh_interval": "1s"}

    @classmethod
    def from_page(cls, page):
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
        return {
            "id": self.meta.id, "title": self.title, "slug": self.slug,
            "author": self.author_username, "updated_at": self.updated_at,
            "snippet": self._highlight_snippet(),
        }

    def _highlight_snippet(self, max_length: int = 200) -> str:
        if hasattr(self.meta, "highlight") and self.meta.highlight:
            return "...".join(self.meta.highlight.body)[:max_length]
        return self.body[:max_length] + "..." if len(self.body) > max_length else self.body
