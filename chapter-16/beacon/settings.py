"""
Beacon v0.16 — The Principles That Remain.

Chapter 16 distills all 22 principles from the journey into a
production-ready Django configuration. Every setting here is the
conclusion of a principle learned the hard way.

Principle 1 (Ch1): Start Simple. This settings file is still a single
Django settings module, not a distributed config system.
Principle 2 (Ch2): Measure Before You Scale. Prometheus + Jaeger.
Principle 3 (Ch3): Cache at the Right Layer. Redis-backed caching.
Principle 4 (Ch4): Async Work. Celery for non-critical work.
Principle 5 (Ch5): Read Replicas. SHARD_MAP supports replica routing.
Principle 6 (Ch6): Shard by Tenant. Org-based sharding via DATABASE_ROUTERS.
Principle 7 (Ch7): Services Own Their Data. gRPC service addresses.
Principle 8 (Ch8): Idempotency. Outbox + idempotency keys.
Principle 9 (Ch9): CRDTs > OT. Channels + Redis for collaboration.
Principle 10 (Ch10): Search is a Service. Elasticsearch config.
Principle 11 (Ch11): Feed via Kafka. Kafka brokers config.
Principle 12 (Ch12): OLTP != OLAP. ClickHouse for analytics.
Principle 13 (Ch13): Multi-Region. Kubernetes-aware config.
Principle 14 (Ch14): Observability. Prometheus + OTEL + structured logging.
Principle 15 (Ch15): Cost Awareness. CDN + FinOps instrumentation.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("SECRET_KEY", "beacon-dev-key-ch16")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","channels","django_celery_results","django_prometheus",
    "storages",
    "core",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.LatencyMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "beacon.urls"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "beacon.wsgi.application"
ASGI_APPLICATION = "beacon.asgi.application"

# Principle 5 (Ch5): Read Replicas.
# Principle 6 (Ch6): Tenant-Based Sharding.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME","beacon"),
        "USER": os.environ.get("DB_USER","beacon"),
        "PASSWORD": os.environ.get("DB_PASSWORD","beacon_dev"),
        "HOST": os.environ.get("DB_HOST","localhost"),
        "PORT": os.environ.get("DB_PORT","5432"),
    }
}
DATABASE_ROUTERS = ["core.sharding.router.OrganizationShardRouter"]

# Principle 3 (Ch3): Redis-backed caching.
CACHES = {"default":{"BACKEND":"django.core.cache.backends.redis.RedisCache","LOCATION":os.environ.get("REDIS_URL","redis://localhost:6379/1")}}

# Principle 4 (Ch4): Celery for async work.
CELERY_BROKER_URL = os.environ.get("REDIS_URL","redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]

# Principle 9 (Ch9): Channels for real-time collaboration.
CHANNEL_LAYERS = {"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[os.environ.get("REDIS_URL","redis://localhost:6379/0")]}}}

# Principle 14 (Ch14): Observability via OpenTelemetry.
OTEL_EXPORTER_JAEGER_AGENT_HOST = os.environ.get("JAEGER_HOST","localhost")
OTEL_EXPORTER_JAEGER_AGENT_PORT = int(os.environ.get("JAEGER_PORT","6831"))

# Principle 15 (Ch15): CDN for cost efficiency.
CDN_ENABLED = os.environ.get("CDN_ENABLED","false").lower() == "true"
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME","beacon-assets")
    AWS_S3_REGION_NAME = os.environ.get("AWS_REGION","us-east-1")

# Principle 10 (Ch10): Elasticsearch for full-text search.
ELASTICSEARCH_HOSTS = os.environ.get("ELASTICSEARCH_HOSTS","http://localhost:9200")

# Principle 11 (Ch11): Kafka for event streaming.
KAFKA_BROKERS = os.environ.get("KAFKA_BROKERS","localhost:9092")

# Principle 12 (Ch12): ClickHouse for analytics.
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST","localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT","9000"))

# Principle 13 (Ch13): Multi-Region Kubernetes awareness.
REGION = os.environ.get("REGION","local")

# Sharding map (populated per deployment)
SHARD_MAP = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
NEWS_API_KEY = os.environ.get("NEWS_API_KEY","")
