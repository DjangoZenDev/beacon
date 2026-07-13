
"""Beacon v0.7 — Scatter-Gather Queries. Carried forward from Ch6."""
import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

logger = logging.getLogger("beacon.queries")
MAX_SHARD_WORKERS = 8


def global_search(query: str, org_ids: list[int], max_results: int = 20) -> list[dict]:
    if not query or not org_ids:
        return []
    org_key = ",".join(str(o) for o in sorted(org_ids))
    cache_key = f"global_search:{hashlib.md5(f'{query}:{org_key}'.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    shard_names = list(getattr(settings, "SHARD_MAP", {}).keys()) or ["default"]
    results = []
    with ThreadPoolExecutor(max_workers=min(len(shard_names), MAX_SHARD_WORKERS)) as executor:
        futures = {executor.submit(_search_shard, s, query, org_ids): s for s in shard_names}
        for future in as_completed(futures):
            try:
                results.extend(future.result(timeout=5))
            except Exception as exc:
                logger.error("Shard search failed: %s", exc)
    results.sort(key=lambda r: r.get("incoming_count", 0), reverse=True)
    results = results[:max_results]
    cache.set(cache_key, results, timeout=300)
    return results


def _search_shard(shard: str, query: str, org_ids: list[int]) -> list[dict]:
    from core.models import Page
    try:
        pages = Page.objects.using(shard).filter(organization_id__in=org_ids).filter(Q(title__icontains=query) | Q(body__icontains=query)).only("title", "slug", "organization_id", "incoming_count").order_by("-incoming_count")[:50]
        return [{"title": p.title, "slug": p.slug, "org_id": p.organization_id, "incoming_count": p.incoming_count, "excerpt": _excerpt(p.body, query) if hasattr(p, "body") and p.body else ""} for p in pages]
    except Exception as exc:
        logger.warning("Search on shard %s failed: %s", shard, exc)
        return []


def _excerpt(body: str, query: str, context_chars: int = 100) -> str:
    if not body or not query:
        return ""
    idx = body.lower().find(query.lower())
    if idx == -1:
        return body[:context_chars]
    start = max(0, idx - context_chars // 2)
    end = min(len(body), idx + len(query) + context_chars // 2)
    snippet = body[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(body):
        snippet = snippet + "..."
    return snippet
