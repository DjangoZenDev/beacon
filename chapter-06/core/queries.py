"""
Beacon v0.6 — Scatter-Gather Queries

Cross-shard queries use the scatter-gather pattern:
1. Scatter: send the query to ALL shards in parallel.
2. Gather: collect results, merge, and return.

This is inherently slower than single-shard queries (each shard adds
network latency), but it's the only way to answer questions that span
organizations, such as global search across all orgs a user belongs to.

Chapter 6, Section 6.9: "Cross-org search initially scattered to all
shards on every request, adding 120ms of latency. The fix was to cache
global search results in Redis with a 5-minute TTL."
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

logger = logging.getLogger("beacon.queries")

MAX_SHARD_WORKERS = 8


def global_search(query: str, org_ids: list[int], max_results: int = 20) -> list[dict]:
    """
    Search across all shards for pages matching the query.

    Uses the scatter-gather pattern: queries each shard in parallel,
    collects results, sorts by relevance (incoming link count), and
    returns the top results.

    Results are cached in Redis with a 5-minute TTL because cross-shard
    searches are expensive (each shard query adds ~30ms network latency).

    Args:
        query: The search query string.
        org_ids: List of organization IDs the user can search within.
        max_results: Maximum number of results to return.

    Returns:
        List of page dicts with title, slug, org_id, excerpt.
    """
    if not query or not org_ids:
        return []

    # Generate a cache key.
    import hashlib
    org_key = ",".join(str(o) for o in sorted(org_ids))
    cache_key = f"global_search:{hashlib.md5(f'{query}:{org_key}'.encode()).hexdigest()}"

    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("global_search cache HIT: %s", cache_key)
        return cached

    logger.debug("global_search cache MISS: %s", cache_key)

    # ── Scatter: query all shards in parallel ────────────────────
    shard_names = list(getattr(settings, "SHARD_MAP", {}).keys())
    if not shard_names:
        shard_names = ["default"]

    results = []
    with ThreadPoolExecutor(max_workers=min(len(shard_names), MAX_SHARD_WORKERS)) as executor:
        futures = {
            executor.submit(_search_shard, shard, query, org_ids): shard
            for shard in shard_names
        }

        for future in as_completed(futures):
            shard = futures[future]
            try:
                shard_results = future.result(timeout=5)
                results.extend(shard_results)
            except Exception as exc:
                logger.error("Shard search failed for %s: %s", shard, exc)

    # ── Gather: sort by relevance, deduplicate, limit ────────────
    results.sort(key=lambda r: r.get("incoming_count", 0), reverse=True)
    results = results[:max_results]

    # Cache for 5 minutes.
    cache.set(cache_key, results, timeout=300)

    return results


def _search_shard(shard: str, query: str, org_ids: list[int]) -> list[dict]:
    """
    Search a single shard for pages matching the query.

    Filters by the organization IDs that exist on this shard.
    Returns a list of lightweight page dicts (not full model instances).
    """
    from core.models import Page

    try:
        pages = (
            Page.objects.using(shard)
            .filter(
                organization_id__in=org_ids,
            )
            .filter(
                Q(title__icontains=query) | Q(body__icontains=query)
            )
            .only("title", "slug", "organization_id", "incoming_count")
            .order_by("-incoming_count")[:50]
        )

        return [
            {
                "title": p.title,
                "slug": p.slug,
                "org_id": p.organization_id,
                "incoming_count": p.incoming_count,
                "excerpt": _excerpt(p.body, query) if hasattr(p, "body") and p.body else "",
            }
            for p in pages
        ]
    except Exception as exc:
        logger.warning("Search on shard %s failed: %s", shard, exc)
        return []


def _excerpt(body: str, query: str, context_chars: int = 100) -> str:
    """Extract a snippet around the first match of the query."""
    if not body or not query:
        return ""
    idx = body.lower().find(query.lower())
    if idx == -1:
        return body[:context_chars]
    start = max(0, idx - context_chars // 2)
    end = min(len(body), idx + len(query) + context_chars // 2)
    snippet = body[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(body):
        snippet = snippet + "…"
    return snippet
