
"""
Beacon v0.7 — Backfill Utility

Carried forward from Chapter 6.
"""
import logging
from django.db import connections
logger = logging.getLogger("beacon.sharding")
BATCH_SIZE = 500


def backfill_orgs(org_ids: list[int], old_shard: str, new_shard: str):
    from core.models import Page, PageLink
    stats = {"pages_copied": 0, "links_copied": 0, "errors": 0}
    total_orgs = len(org_ids)
    logger.info("Starting backfill: %d organizations from %s to %s", total_orgs, old_shard, new_shard)
    for idx, org_id in enumerate(org_ids):
        try:
            logger.info("Backfill org %d (%d/%d) ...", org_id, idx + 1, total_orgs)
            pages = list(Page.objects.using(old_shard).filter(organization_id=org_id).values())
            for i in range(0, len(pages), BATCH_SIZE):
                batch = pages[i:i + BATCH_SIZE]
                _bulk_insert_pages(batch, new_shard)
                stats["pages_copied"] += len(batch)
            links = list(PageLink.objects.using(old_shard).filter(organization_id=org_id).values())
            for i in range(0, len(links), BATCH_SIZE):
                batch = links[i:i + BATCH_SIZE]
                _bulk_insert_links(batch, new_shard)
                stats["links_copied"] += len(batch)
            _verify_counts(org_id, old_shard, new_shard, len(pages), len(links))
        except Exception as exc:
            logger.error("Backfill failed for org %d: %s", org_id, exc)
            stats["errors"] += 1
    logger.info("Backfill complete: %d pages, %d links, %d errors", stats["pages_copied"], stats["links_copied"], stats["errors"])
    return stats


def _bulk_insert_pages(rows, shard):
    if not rows:
        return
    with connections[shard].cursor() as cursor:
        for row in rows:
            cursor.execute("""INSERT INTO core_page (id, organization_id, title, slug, body, author_id, created_at, updated_at, incoming_count, outgoing_count) VALUES (%(id)s, %(organization_id)s, %(title)s, %(slug)s, %(body)s, %(author_id)s, %(created_at)s, %(updated_at)s, %(incoming_count)s, %(outgoing_count)s) ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, updated_at=EXCLUDED.updated_at, incoming_count=EXCLUDED.incoming_count, outgoing_count=EXCLUDED.outgoing_count""", row)


def _bulk_insert_links(rows, shard):
    if not rows:
        return
    with connections[shard].cursor() as cursor:
        for row in rows:
            cursor.execute("""INSERT INTO core_pagelink (id, organization_id, source_id, target_id, created_at) VALUES (%(id)s, %(organization_id)s, %(source_id)s, %(target_id)s, %(created_at)s) ON CONFLICT DO NOTHING""", row)


def _verify_counts(org_id, old_shard, new_shard, expected_pages, expected_links):
    from core.models import Page, PageLink
    new_pages = Page.objects.using(new_shard).filter(organization_id=org_id).count()
    new_links = PageLink.objects.using(new_shard).filter(organization_id=org_id).count()
    if new_pages != expected_pages:
        logger.warning("Page count mismatch for org %d: expected %d, got %d", org_id, expected_pages, new_pages)
    if new_links != expected_links:
        logger.warning("Link count mismatch for org %d: expected %d, got %d", org_id, expected_links, new_links)
    if new_pages == expected_pages and new_links == expected_links:
        logger.info("Org %d verification OK: %d pages, %d links", org_id, new_pages, new_links)
