"""Beacon v0.14 — Queries, Serializers, Search, InvertedIndex, Models, PageViewTracker — carry-forward batch."""

# ── queries.py ──
import logging, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings; from django.core.cache import cache; from django.db.models import Q
logger = logging.getLogger("beacon.queries")
def global_search(query, org_ids, max_results=20):
    if not query or not org_ids: return []
    org_key = ",".join(str(o) for o in sorted(org_ids))
    cache_key = f"global_search:{hashlib.md5(f'{query}:{org_key}'.encode()).hexdigest()}"
    cached = cache.get(cache_key); 
    if cached is not None: return cached
    shards = list(getattr(settings,"SHARD_MAP",{}).keys()) or ["default"]; results = []
    with ThreadPoolExecutor(max_workers=min(len(shards),8)) as ex:
        futures = {ex.submit(_search_shard,s,query,org_ids):s for s in shards}
        for f in as_completed(futures):
            try: results.extend(f.result(timeout=5))
            except Exception as exc: logger.error("Shard search failed: %s", exc)
    results.sort(key=lambda r: r.get("incoming_count",0), reverse=True); results = results[:max_results]
    cache.set(cache_key, results, timeout=300); return results
def _search_shard(shard, query, org_ids):
    from core.models import Page
    try:
        pages = Page.objects.using(shard).filter(organization_id__in=org_ids).filter(Q(title__icontains=query)|Q(body__icontains=query)).only("title","slug","organization_id","incoming_count").order_by("-incoming_count")[:50]
        return [{"title":p.title,"slug":p.slug,"org_id":p.organization_id,"incoming_count":p.incoming_count,"excerpt":_excerpt(p.body,query) if hasattr(p,"body") and p.body else ""} for p in pages]
    except Exception as exc: logger.warning("Search shard %s failed: %s", exc); return []
def _excerpt(body, query, ctx=100):
    if not body or not query: return ""
    idx = body.lower().find(query.lower()); 
    if idx == -1: return body[:ctx]
    s = max(0, idx - ctx//2); e = min(len(body), idx + len(query) + ctx//2)
    return ("..." if s>0 else "") + body[s:e] + ("..." if e<len(body) else "")
