
"""
Beacon v0.6 — Middleware

Unchanged from Chapter 5. LatencyMiddleware tracks request duration;
QueryCountMiddleware warns when >20 queries per request.
"""

import logging
import time

from django.db import connection

logger = logging.getLogger("beacon.latency")
query_logger = logging.getLogger("beacon.queries")


class LatencyMiddleware:
    """
    Measure and log request duration.
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
    Count database queries per request and log when >20.
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
