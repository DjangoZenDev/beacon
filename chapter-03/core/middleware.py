"""
Beacon v0.3 — Middleware

Unchanged from Chapter 2. The QueryCountMiddleware continues to log
when requests make more than 20 SQL queries. With Redis caching active,
the query count for page views should drop to 1-2 queries per request
instead of the 20+ seen in Chapter 2.
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

    DEVELOPMENT ONLY. A request making more than 20 queries triggers
    a warning. With Chapter 3 caching, most page views should be
    well under this threshold.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
