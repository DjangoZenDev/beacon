
"""
Beacon v0.14 — Prometheus Metrics
Chapter 14: Observability — Custom application metrics.

Exposes counters, histograms, and gauges for Prometheus scraping
via django-prometheus on the /metrics endpoint.

Metrics defined:
- page_views_total: Counter, labeled by page_slug and organization_id.
- page_edits_total: Counter, labeled by page_slug and user_id.
- request_duration_seconds: Histogram, labeled by view_name and method.
- active_users: Gauge, current count of active WebSocket connections.
"""

from prometheus_client import Counter, Histogram, Gauge, Info


# ── Counters ──────────────────────────────────────────────────

page_views_total = Counter(
    "beacon_page_views_total",
    "Total number of page views",
    ["page_slug", "organization_id", "region"],
)

page_edits_total = Counter(
    "beacon_page_edits_total",
    "Total number of page edits",
    ["page_slug", "user_id", "region"],
)

search_queries_total = Counter(
    "beacon_search_queries_total",
    "Total number of search queries executed",
    ["query_type", "region"],  # query_type: elasticsearch | postgres
)

outbox_messages_published = Counter(
    "beacon_outbox_messages_published_total",
    "Total number of outbox messages published to Kafka",
    ["topic", "status"],
)

# ── Histograms ────────────────────────────────────────────────

request_duration_seconds = Histogram(
    "beacon_request_duration_seconds",
    "Request duration in seconds",
    ["view_name", "method", "region"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

db_query_duration_seconds = Histogram(
    "beacon_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "shard"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

cache_operation_duration_seconds = Histogram(
    "beacon_cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation", "backend"],
    buckets=[0.0001, 0.001, 0.005, 0.01, 0.05],
)

# ── Gauges ────────────────────────────────────────────────────

active_users = Gauge(
    "beacon_active_users",
    "Current number of active users (WebSocket connections)",
    ["region"],
)

crdt_document_count = Gauge(
    "beacon_crdt_document_count",
    "Number of CRDT documents currently in Redis",
    ["region"],
)

kafka_consumer_lag = Gauge(
    "beacon_kafka_consumer_lag",
    "Kafka consumer group lag (messages behind)",
    ["topic", "consumer_group", "region"],
)

# ── Info ──────────────────────────────────────────────────────

build_info = Info(
    "beacon_build",
    "Beacon application build information",
)
build_info.info({
    "version": "0.14.0",
    "chapter": "14",
    "runtime": "python",
})


# ── Metric Helpers ────────────────────────────────────────────

def record_page_view(page_slug: str, organization_id: int, region: str = ""):
    """Increment the page_views_total counter."""
    page_views_total.labels(
        page_slug=page_slug,
        organization_id=str(organization_id),
        region=region or _get_region(),
    ).inc()


def record_page_edit(page_slug: str, user_id: int, region: str = ""):
    """Increment the page_edits_total counter."""
    page_edits_total.labels(
        page_slug=page_slug,
        user_id=str(user_id),
        region=region or _get_region(),
    ).inc()


def record_request_duration(view_name: str, method: str, duration_s: float, region: str = ""):
    """Observe request duration in the histogram."""
    request_duration_seconds.labels(
        view_name=view_name,
        method=method,
        region=region or _get_region(),
    ).observe(duration_s)


def _get_region() -> str:
    """Get the current region from the environment."""
    import os
    return os.environ.get("REGION", "unknown")
