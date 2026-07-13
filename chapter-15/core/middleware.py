"Beacon v0.15 — Middleware."
import time, logging
logger = logging.getLogger("beacon.latency")

class LatencyMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"
        if duration_ms > 200:
            logger.warning("Slow request: %s %s (%.0f ms)", request.method, request.path, duration_ms)
        return response
