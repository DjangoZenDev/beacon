"""Beacon v0.14 — PageView Tracker (carried from Ch12)."""
import logging, time
from django.utils import timezone
logger = logging.getLogger("beacon.analytics")

class PageViewTracker:
    def __init__(self, get_response=None): self.get_response = get_response
    def __call__(self, request):
        start = time.time(); response = self.get_response(request) if self.get_response else None
        duration = time.time() - start
        if request and hasattr(request, "resolver_match"): self.record_view(request, duration_seconds=int(duration))
        return response
    def record_view(self, request, duration_seconds=0):
        try:
            from core.outbox import enqueue_outbox; from core.metrics import record_page_view
            page_slug = None
            if hasattr(request, "resolver_match") and request.resolver_match: page_slug = request.resolver_match.kwargs.get("slug")
            if not page_slug or request.path.startswith("/admin") or request.path.startswith("/api"): return
            user_id = request.user.pk if request.user.is_authenticated else 0
            username = request.user.username if request.user.is_authenticated else "anonymous"
            payload = {"type":"page.viewed","payload":{"page_slug":page_slug,"user_id":user_id,"user_username":username,"organization_id":getattr(request.user,"organization_id",1) if request.user.is_authenticated else 1,"duration_seconds":duration_seconds,"referrer":request.META.get("HTTP_REFERER",""),"timestamp":timezone.now().isoformat()}}
            enqueue_outbox("beacon.events.page_views", payload)
            record_page_view(page_slug, getattr(request.user,"organization_id",1))
            logger.debug("Page view recorded: slug=%s user=%s", page_slug, username)
        except Exception as exc: logger.warning("Failed to record page view: %s", exc)
