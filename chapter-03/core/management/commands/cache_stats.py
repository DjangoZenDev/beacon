"""
Beacon v0.3 — cache_stats management command

Prints Redis cache statistics including hit rate, memory usage,
and Beacon-specific counts of cached pages and page lists.

Usage:
    python manage.py cache_stats

Example output:
    Connected clients: 11
    Used memory: 24.3M
    Keyspace hits: 3,421,887
    Keyspace misses: 47,231
    Cache hit rate: 98.6%
    Cached pages: 8,412
    Cached page lists: 421
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print Redis cache statistics including hit rate and key counts."

    def handle(self, *args, **options):
        try:
            client = cache.client.get_client()
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"Cannot connect to Redis: {e}"
            ))
            return

        # Redis INFO command returns server statistics.
        info = client.info()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── Redis Cache Statistics ──"))
        self.stdout.write("")

        self.stdout.write(f"  Connected clients : {info.get('connected_clients', 'N/A')}")
        self.stdout.write(f"  Used memory       : {info.get('used_memory_human', 'N/A')}")
        self.stdout.write(f"  Uptime (seconds)  : {info.get('uptime_in_seconds', 'N/A')}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── Hit Rate ──"))
        self.stdout.write("")

        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses

        self.stdout.write(f"  Keyspace hits     : {hits:,}")
        self.stdout.write(f"  Keyspace misses   : {misses:,}")

        if total > 0:
            hit_rate = (hits / total) * 100
            # Color-code: green >80%, yellow >50%, red <=50%
            if hit_rate > 80:
                rate_style = self.style.SUCCESS
            elif hit_rate > 50:
                rate_style = self.style.WARNING
            else:
                rate_style = self.style.ERROR
            self.stdout.write(rate_style(
                f"  Cache hit rate    : {hit_rate:.1f}%"
            ))
        else:
            self.stdout.write("  Cache hit rate    : N/A (no operations recorded)")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── Beacon-Specific Key Counts ──"))
        self.stdout.write("")

        # Count cached page detail entries.
        try:
            page_keys = list(cache.iter_keys("page:*"))
            # Filter out page_list keys which also start with "page:"
            page_keys = [k for k in page_keys if not isinstance(k, str) or not k.startswith("page_list")]
            page_count = len(page_keys)
        except Exception:
            page_count = "N/A (iter_keys not supported)"

        # Count cached page list entries.
        try:
            list_keys = list(cache.iter_keys("page_list:*"))
            list_count = len(list_keys)
        except Exception:
            list_count = "N/A (iter_keys not supported)"

        self.stdout.write(f"  Cached pages      : {page_count}")
        self.stdout.write(f"  Cached page lists : {list_count}")

        self.stdout.write("")

        # Evicted keys.
        evicted = info.get("evicted_keys", 0)
        if evicted > 0:
            self.stdout.write(self.style.WARNING(
                f"  Evicted keys      : {evicted:,} (Redis is under memory pressure)"
            ))

        # Key expiry.
        expired = info.get("expired_keys", 0)
        if expired > 0:
            self.stdout.write(f"  Expired keys      : {expired:,}")
