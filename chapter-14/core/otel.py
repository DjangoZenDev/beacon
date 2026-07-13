
"""
Beacon v0.14 — OpenTelemetry Setup
Chapter 14: Observability — OpenTelemetry tracing with Jaeger exporter.

Sets up the TracerProvider, JaegerExporter, DjangoInstrumentor,
and a BatchSpanProcessor for efficient span export.

Principle: "The trace ID is the golden thread."
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from django.conf import settings


def init_otel(service_name: str = "beacon"):
    """
    Initialize OpenTelemetry for the Beacon application.

    Sets up:
    - TracerProvider with service name and region as resource attributes.
    - JaegerExporter for trace export (agent or collector mode).
    - DjangoInstrumentor for automatic Django request/response spans.
    - Redis, PostgreSQL, and HTTP client instrumentors.
    - LoggingInstrumentor to inject trace_id into log records.

    Args:
        service_name: The service name reported to Jaeger.

    Call once at Django startup (e.g., in AppConfig.ready()).
    """

    # Resource identifies this service instance.
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "deployment.environment": os.environ.get("DEPLOY_ENV", "production"),
        "region": os.environ.get("REGION", "unknown"),
    })

    # TracerProvider is the entry point for the SDK.
    provider = TracerProvider(resource=resource)

    # Jaeger exporter — sends spans to Jaeger agent or collector.
    jaeger_host = os.environ.get("JAEGER_HOST", "localhost")
    jaeger_port = int(os.environ.get("JAEGER_PORT", "6831"))

    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )

    # BatchSpanProcessor: buffers spans and exports in batches.
    # Reduces network overhead vs. SimpleSpanProcessor.
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

    # Also log spans to console in development.
    if os.environ.get("OTEL_LOG_SPANS", "").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Set the global TracerProvider.
    trace.set_tracer_provider(provider)

    # ── Auto-Instrumentation ──────────────────────────────────

    # Django: request/response spans, middleware hooks.
    DjangoInstrumentor().instrument(
        is_sql_commentor_enabled=True,  # Adds SQL comments for trace correlation.
    )

    # Redis: cache operations.
    RedisInstrumentor().instrument()

    # PostgreSQL: database queries.
    Psycopg2Instrumentor().instrument()

    # HTTP client: outgoing requests (e.g., to external APIs).
    RequestsInstrumentor().instrument()

    # Logging: inject trace_id and span_id into log records.
    LoggingInstrumentor().instrument(set_logging_format=True)

    # Get a tracer for manual instrumentation.
    tracer = trace.get_tracer(__name__)
    tracer.info("OpenTelemetry initialized for service=%s", service_name)


def get_tracer(name: str = "beacon"):
    """
    Get a tracer for manual span creation.

    Args:
        name: The instrumentation scope name.

    Returns:
        An OpenTelemetry Tracer instance.

    Usage:
        tracer = get_tracer("beacon.search")
        with tracer.start_as_current_span("search_query") as span:
            span.set_attribute("query.text", q)
            results = do_search(q)
    """
    return trace.get_tracer(name)
