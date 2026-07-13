"""
Beacon v0.2 — Middleware

Chapter 2 adds QueryCountMiddleware: a development-only middleware that
logs the number of SQL queries per request. This is how Maya discovered
the N+1 problem in the first place.

In production, this middleware is removed — counting queries adds ~1ms
overhead per request. Use the LatencyMiddleware for production monitoring.
"""

import logging
import time

from django.db import connection

logger = logging.getLogger("beacon.latency")
query_logger = logging.getLogger("beacon.queries")


class LatencyMiddleware:
    """
    Measure and log request duration.

    Unchanged from Chapter 1. The X-Request-Duration-Ms header is
    scraped by monitoring infrastructure starting in Chapter 14.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"

        if duration_ms > 200:
            logger.warning(
                "Slow request: %s %s (%.0f ms)",
                request.method,
                request.path,
                duration_ms,
            )

        return response


class QueryCountMiddleware:
    """
    Count database queries per request and log them.

    DEVELOPMENT ONLY. This middleware counts the number of SQL queries
    executed during a request by recording connection.queries before and
    after the view runs.

    A request making more than 20 queries triggers a warning. Each extra
    query is a potential N+1 problem — the query plan should be examined
    with Django Debug Toolbar or Silk.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Reset the query log for this request.
        initial_count = len(connection.queries)

        response = self.get_response(request)

        final_count = len(connection.queries)
        query_count = final_count - initial_count

        if query_count > 20:
            query_logger.warning(
                "High query count: %s %s — %d queries",
                request.method,
                request.path,
                query_count,
            )

        return response
