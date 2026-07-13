
"""
Beacon v0.12 — Page View Tracker

Middleware that records PageView events to the outbox for CDC.
Each page view is written to the outbox table within the request
transaction, then picked up by the outbox poller and published
to Kafka (beacon.events.page_views).

Chapter 13: Carried forward — works identically in multi-region.
Outbox messages in each region flow to that region's Kafka cluster.
Cross-region analytics aggregation happens at the ClickHouse layer.
"""

import json
import logging
import time

from django.utils import timezone

logger = logging.getLogger("beacon.analytics")


class PageViewTracker:
    """Records page view events for analytics."""

    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request) if self.get_response else None
        duration = time.time() - start
        if request and hasattr(request, "resolver_match"):
            self.record_view(request, duration_seconds=int(duration))
        return response

    def record_view(self, request, duration_seconds: int = 0):
        try:
            from core.outbox import enqueue_outbox
            page_slug = None
            if hasattr(request, "resolver_match") and request.resolver_match:
                page_slug = request.resolver_match.kwargs.get("slug")
            if not page_slug or request.path.startswith("/admin") or request.path.startswith("/api"):
                return
            user_id = request.user.pk if request.user.is_authenticated else 0
            username = request.user.username if request.user.is_authenticated else "anonymous"
            payload = {
                "type": "page.viewed",
                "payload": {
                    "page_slug": page_slug, "user_id": user_id,
                    "user_username": username,
                    "organization_id": getattr(request.user, "organization_id", 1) if request.user.is_authenticated else 1,
                    "duration_seconds": duration_seconds,
                    "referrer": request.META.get("HTTP_REFERER", ""),
                    "timestamp": timezone.now().isoformat(),
                },
            }
            enqueue_outbox("beacon.events.page_views", payload)
            logger.debug("Page view recorded: slug=%s user=%s", page_slug, username)
        except Exception as exc:
            logger.warning("Failed to record page view: %s", exc)


def track_page_view(request, page, duration_seconds: int = 0):
    """Convenience function to record a page view from a view."""
    try:
        from core.outbox import enqueue_outbox
        user_id = request.user.pk if request.user.is_authenticated else 0
        username = request.user.username if request.user.is_authenticated else "anonymous"
        payload = {
            "type": "page.viewed",
            "payload": {
                "page_id": page.pk, "page_slug": page.slug, "page_title": page.title,
                "user_id": user_id, "user_username": username,
                "organization_id": page.organization_id,
                "duration_seconds": duration_seconds,
                "referrer": request.META.get("HTTP_REFERER", ""),
                "timestamp": timezone.now().isoformat(),
            },
        }
        enqueue_outbox("beacon.events.page_views", payload)
        logger.debug("Page view recorded: page=%s user=%s", page.pk, username)
    except Exception as exc:
        logger.warning("Failed to record page view: %s", exc)
