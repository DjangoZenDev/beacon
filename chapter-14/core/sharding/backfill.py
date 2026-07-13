"""Beacon v0.14 — Backfill."""
import logging; from django.db import connections
logger = logging.getLogger("beacon.sharding"); BATCH_SIZE = 500
def backfill_orgs(org_ids, old_shard, new_shard):
    from core.models import Page, PageLink
    stats = {"pages_copied":0,"links_copied":0,"errors":0}
    for org_id in org_ids:
        try:
            pages = list(Page.objects.using(old_shard).filter(organization_id=org_id).values())
            for i in range(0,len(pages),BATCH_SIZE): _bulk_pages(pages[i:i+BATCH_SIZE],new_shard); stats["pages_copied"] += len(pages[i:i+BATCH_SIZE])
            links = list(PageLink.objects.using(old_shard).filter(organization_id=org_id).values())
            for i in range(0,len(links),BATCH_SIZE): _bulk_links(links[i:i+BATCH_SIZE],new_shard); stats["links_copied"] += len(links[i:i+BATCH_SIZE])
        except Exception as exc: logger.error("Backfill org %d failed: %s", org_id, exc); stats["errors"] += 1
    return stats
def _bulk_pages(rows, shard):
    if not rows: return
    with connections[shard].cursor() as c:
        for r in rows: c.execute("INSERT INTO core_page (id,organization_id,title,slug,body,author_id,created_at,updated_at,incoming_count,outgoing_count) VALUES (%(id)s,%(organization_id)s,%(title)s,%(slug)s,%(body)s,%(author_id)s,%(created_at)s,%(updated_at)s,%(incoming_count)s,%(outgoing_count)s) ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title,body=EXCLUDED.body,updated_at=EXCLUDED.updated_at", r)
def _bulk_links(rows, shard):
    if not rows: return
    with connections[shard].cursor() as c:
        for r in rows: c.execute("INSERT INTO core_pagelink (id,organization_id,source_id,target_id,created_at) VALUES (%(id)s,%(organization_id)s,%(source_id)s,%(target_id)s,%(created_at)s) ON CONFLICT DO NOTHING", r)
