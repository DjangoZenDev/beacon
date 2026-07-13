"""
Beacon v0.1 — Middleware

Chapter 1 introduces a single custom middleware: LatencyMiddleware.

It measures the wall-clock time for every request and appends the
duration as an X-Request-Duration-Ms response header. This is the
simplest possible observability — no Prometheus, no tracing, no
structured logging. Those arrive in Chapter 14.

The measurement happens at the Django middleware level, which means it
captures the full request lifecycle: middleware chain → URL routing →
view execution → template rendering → response. It does NOT capture
network time between the client and the server, which is usually the
dominant factor.
"""

import time
import logging

logger = logging.getLogger("beacon.latency")


class LatencyMiddleware:
    """
    Measure request duration and attach it as a response header.

    In production, this header can be scraped by a load balancer or
    monitoring agent. For now, it is visible in browser DevTools.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"

        # Log slow requests (threshold: 200 ms — Beacon's latency budget).
        if duration_ms > 200:
            logger.warning(
                "Slow request: %s %s (%.0f ms)",
                request.method,
                request.path,
                duration_ms,
            )

        return response
