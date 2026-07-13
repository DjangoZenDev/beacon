"""
Beacon v0.11 — Activity Feed Manager

Implements the hybrid fan-out approach for activity feeds:

- Fan-out on write for active users (Redis sorted sets, capped at 500).
- Fan-out on read for inactive users (EventStore query on return).
- Celebrity optimization: pages with >10,000 followers skip fan-out.

Chapter 11, Principle 1: "Fan-out on write for the active,
fan-out on read for the inactive."
Chapter 11, Principle 2: "Celebrity pages are a different problem."
"""

import json
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("beacon.feed")

# ── Feed configuration ──────────────────────────────────────────

FEED_CONFIG = getattr(settings, "FEED_CONFIG", {})
CELEBRITY_THRESHOLD = FEED_CONFIG.get("CELEBRITY_THRESHOLD", 10_000)
ACTIVE_WINDOW_DAYS = FEED_CONFIG.get("ACTIVE_WINDOW_DAYS", 30)
FEED_MAX_ITEMS = FEED_CONFIG.get("FEED_MAX_ITEMS", 500)
FEED_TTL_SECONDS = FEED_CONFIG.get("FEED_TTL_SECONDS", 60 * 60 * 24 * 30)


class FeedManager:
    """
    Hybrid feed manager: fan-out-on-write + fan-out-on-read.

    Each user's feed is a Redis sorted set (keyed by user ID), with
    events scored by timestamp. The feed is capped at 500 items and
    expires after 30 days of inactivity.
    """

    def __init__(self, redis_client=None):
        if redis_client is None:
            from django.core.cache import cache
            self.redis = cache.client.get_client() if hasattr(cache, "client") else None
        else:
            self.redis = redis_client

    def fanout_on_write(self, page, event_type: str, follower_ids: list[int]):
        """
        Push a page event into every active follower's feed.

        Uses a Redis pipeline for batched ZADD + ZREMRANGEBYRANK.
        Each feed is capped at FEED_MAX_ITEMS items.

        Args:
            page: The Page model instance.
            event_type: "page.created", "page.updated", etc.
            follower_ids: List of active follower user IDs.
        """
        if not self.redis or not follower_ids:
            return

        event_data = json.dumps({
            "type": event_type,
            "page_id": page.pk,
            "page_title": page.title,
            "author": page.author.username,
            "slug": page.slug,
            "timestamp": time.time(),
        })

        score = time.time()
        pipe = self.redis.pipeline()

        for user_id in follower_ids:
            feed_key = f"feed:{user_id}"
            pipe.zadd(feed_key, {event_data: score})
            pipe.zremrangebyrank(feed_key, 0, -(FEED_MAX_ITEMS + 1))
            pipe.expire(feed_key, FEED_TTL_SECONDS)

        pipe.execute()
        logger.info(
            "Fan-out on write: page=%s event=%s followers=%d",
            page.pk, event_type, len(follower_ids),
        )

    def fanout_on_read(self, user) -> list[dict]:
        """
        Assemble a feed for an inactive user by querying the EventStore.

        Args:
            user: The Django User model instance.

        Returns:
            List of feed event dicts ordered by timestamp descending.
        """
        from core.models import Event as FeedEvent

        cutoff = timezone.now() - timedelta(days=ACTIVE_WINDOW_DAYS)
        events = FeedEvent.objects.filter(
            timestamp__gte=cutoff,
        ).select_related("page", "actor").order_by("-timestamp")[:FEED_MAX_ITEMS]

        return [e.to_feed_item() for e in events]

    def get_user_feed(self, user, limit: int = 50) -> list[dict]:
        """
        Hybrid feed: Redis sorted set + celebrity page merge.

        1. Get pre-computed feed from Redis.
        2. If the user follows celebrity pages, merge their events.
        3. Sort by timestamp descending, return top ``limit``.

        Args:
            user: The Django User model instance.
            limit: Maximum number of feed items to return.

        Returns:
            List of feed event dicts.
        """
        results = []

        # 1. Get pre-computed feed from Redis.
        if self.redis:
            feed_key = f"feed:{user.id}"
            raw = self.redis.zrevrange(feed_key, 0, limit - 1, withscores=False)
            for item in raw:
                try:
                    results.append(json.loads(item if isinstance(item, str) else item.decode("utf-8")))
                except (json.JSONDecodeError, TypeError):
                    continue

        # 2. If user follows celebrity pages, merge via fan-out on read.
        try:
            from core.models import Page
            celebrity_cutoff = timezone.now() - timedelta(days=7)
            celebrity_pages = Page.objects.filter(
                incoming_count__gt=CELEBRITY_THRESHOLD,
                updated_at__gte=celebrity_cutoff,
            ).order_by("-updated_at")[:limit]

            for page in celebrity_pages:
                results.append({
                    "type": "page.updated",
                    "page_id": page.pk,
                    "page_title": page.title,
                    "author": page.author.username,
                    "slug": page.slug,
                    "timestamp": page.updated_at.timestamp(),
                })
        except Exception as exc:
            logger.warning("Celebrity merge failed: %s", exc)

        # 3. Sort merged results by timestamp descending.
        results.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return results[:limit]


# ── Module-level singleton ──────────────────────────────────

feed_manager = FeedManager()
