"""
Beacon v0.12 — Page View Tracker

Middleware that records PageView events to the outbox for CDC.
Each page view is written to the outbox table within the request
transaction, then picked up by the outbox poller and published
to Kafka (beacon.events.page_views).

This is the C in CQRS: the write side records commands; the read
side (ClickHouse, Iceberg) is updated asynchronously via CDC.

Chapter 12, Principle 1: "OLTP and OLAP are different workloads."
  PostgreSQL serves the user. ClickHouse answers questions.
  CDC is the bridge between them.
"""

import json
import logging
import time

from django.utils import timezone

logger = logging.getLogger("beacon.analytics")


class PageViewTracker:
    """
    Records page view events for analytics.

    Used as a middleware or view mixin. Each page view creates
    an outbox message that eventually flows through Kafka into
    ClickHouse and the data lake (Iceberg).
    """

    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        """Django middleware interface."""
        start = time.time()
        response = self.get_response(request) if self.get_response else None
        duration = time.time() - start

        if request and hasattr(request, "resolver_match"):
            self.record_view(request, duration_seconds=int(duration))

        return response

    def record_view(self, request, duration_seconds: int = 0):
        """
        Record a page view event to the outbox.

        Args:
            request: The Django HttpRequest object.
            duration_seconds: Time spent rendering the response.
        """
        try:
            from core.outbox import enqueue_outbox

            # Extract page info from the resolved URL.
            page_slug = None
            if hasattr(request, "resolver_match") and request.resolver_match:
                page_slug = request.resolver_match.kwargs.get("slug")

            # Only record views of actual pages (not admin, API, etc.).
            if not page_slug or request.path.startswith("/admin") or request.path.startswith("/api"):
                return

            user_id = request.user.pk if request.user.is_authenticated else 0
            username = request.user.username if request.user.is_authenticated else "anonymous"

            payload = {
                "type": "page.viewed",
                "payload": {
                    "page_slug": page_slug,
                    "user_id": user_id,
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
    """
    Convenience function to record a page view from a view.

    Args:
        request: The Django HttpRequest object.
        page: The Page model instance being viewed.
        duration_seconds: Time spent on the request.
    """
    try:
        from core.outbox import enqueue_outbox

        user_id = request.user.pk if request.user.is_authenticated else 0
        username = request.user.username if request.user.is_authenticated else "anonymous"

        payload = {
            "type": "page.viewed",
            "payload": {
                "page_id": page.pk,
                "page_slug": page.slug,
                "page_title": page.title,
                "user_id": user_id,
                "user_username": username,
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
