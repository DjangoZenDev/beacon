"""Beacon v0.9 — Middleware (carried from Ch5-8)."""
import logging, time
from django.db import connection
logger = logging.getLogger("beacon.latency")
query_logger = logging.getLogger("beacon.queries")

class LatencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{ms:.2f}"
        if ms > 200:
            logger.warning("Slow: %s %s (%.0f ms)", request.method, request.path, ms)
        return response

class QueryCountMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        initial = len(connection.queries)
        response = self.get_response(request)
        count = len(connection.queries) - initial
        if count > 20:
            query_logger.warning("High queries: %s %s — %d", request.method, request.path, count)
        return response
