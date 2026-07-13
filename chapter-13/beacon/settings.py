"""
Beacon v0.13 settings — Chapter 13: Multi-Region / Kubernetes.

Chapter 13 deploys Beacon across three continents: us-east (NA),
eu-west (EU), ap-south (Asia). Each region runs a complete k3s
cluster with CockroachDB for geo-distributed SQL, Istio for service
mesh, and the CRDT engine running globally.

Key additions:
  - CSRF_TRUSTED_ORIGINS for multi-region load balancers
  - ALLOWED_HOSTS for all regional ingress domains
  - DATABASES configured for regional CockroachDB nodes
  - Redis cluster config for each region
  - Kafka across regions with MirrorMaker
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "django-insecure-beacon-ch13-dev-key-change-in-production"
DEBUG = False

# ── Multi-Region Hosts ──────────────────────────────────────
# Ch13: Accept traffic from all regional LBs and the Istio gateway
ALLOWED_HOSTS = [
    ".beacon.internal",           # Cluster-local DNS
    "beacon.example.com",         # Primary domain
    "us-east.beacon.example.com", # North America
    "eu-west.beacon.example.com", # Europe
    "ap-south.beacon.example.com",# Asia-Pacific
    "localhost", "127.0.0.1",
]

# Ch13: Trust CSRF from all regional origins and the gateway
CSRF_TRUSTED_ORIGINS = [
    "https://beacon.example.com",
    "https://us-east.beacon.example.com",
    "https://eu-west.beacon.example.com",
    "https://ap-south.beacon.example.com",
    "https://*.beacon.internal",
]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django_celery_results", "rest_framework", "channels", "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.LatencyMiddleware",
    "core.middleware.QueryCountMiddleware",
    "core.pageview_tracker.PageViewTracker",
]

ROOT_URLCONF = "beacon.urls"
WSGI_APPLICATION = "beacon.wsgi.application"
ASGI_APPLICATION = "beacon.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

# ── Regional CockroachDB Config (Ch13) ─────────────────────
# Each region has its own CockroachDB nodes. The global tables
# (pages, page_links) use CockroachDB's geo-partitioning with
# REGIONAL BY ROW on organization region.
#
# Principle 18: "Global consistency costs latency."
#   CockroachDB spans regions. Write latency = RTT to nearest
#   + RTT to leaseholder. Read latency = RTT to nearest if
#   follower reads enabled.
#
# DATABASES connects to the local-region CockroachDB node.
# Cross-region writes go through CockroachDB's internal
# transaction protocol (parallel commits across leaseholders).

# Determine current region from env; default to us-east.
BEACON_REGION = os.environ.get("BEACON_REGION", "us-east")

REGIONAL_DB_HOSTS = {
    "us-east":  "cockroachdb-us-east.beacon-prod.svc.cluster.local",
    "eu-west":  "cockroachdb-eu-west.beacon-prod.svc.cluster.local",
    "ap-south": "cockroachdb-ap-south.beacon-prod.svc.cluster.local",
}

CRDB_HOST = os.environ.get("CRDB_HOST", REGIONAL_DB_HOSTS.get(BEACON_REGION, "localhost"))
CRDB_PORT = os.environ.get("CRDB_PORT", "26257")

SHARD_MAP = {
    "shard-0": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard0", "USER": "beacon",
        "PASSWORD": "beacon_dev_password", "HOST": "192.168.1.20",
        "PORT": "5432", "CONN_MAX_AGE": 600,
    },
    "shard-1": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard1", "USER": "beacon",
        "PASSWORD": "beacon_dev_password", "HOST": "192.168.1.21",
        "PORT": "5432", "CONN_MAX_AGE": 600,
    },
    "shard-2": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard2", "USER": "beacon",
        "PASSWORD": "beacon_dev_password", "HOST": "192.168.1.22",
        "PORT": "5432", "CONN_MAX_AGE": 600,
    },
    "shard-3": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard3", "USER": "beacon",
        "PASSWORD": "beacon_dev_password", "HOST": "192.168.1.23",
        "PORT": "5432", "CONN_MAX_AGE": 600,
    },
}

DATABASES = {
    # Ch13: "default" now points to the local-region CockroachDB node.
    # The Django ORM sees a single PostgreSQL-compatible endpoint;
    # CockroachDB handles cross-region replication internally.
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon",
        "USER": "beacon",
        "PASSWORD": os.environ.get("CRDB_PASSWORD", "beacon_dev_password"),
        "HOST": CRDB_HOST,
        "PORT": CRDB_PORT,
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            # CockroachDB-specific: disable server-side cursors
            "options": "-c default_transaction_read_only=off",
        },
    },
    # Legacy replica — kept for compatibility during migration.
    "replica": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon",
        "USER": "beacon_readonly",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.11",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"options": "-c default_transaction_read_only=on"},
    },
    # Regional-specific databases for latency-optimized reads.
    f"crdb-{BEACON_REGION}": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon",
        "USER": "beacon",
        "PASSWORD": os.environ.get("CRDB_PASSWORD", "beacon_dev_password"),
        "HOST": CRDB_HOST,
        "PORT": CRDB_PORT,
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    },
}
DATABASES.update(SHARD_MAP)

DATABASE_ROUTERS = ["core.sharding.router.OrganizationShardRouter"]

# ── Redis (Ch13) ────────────────────────────────────────────
# Each region has a local Redis instance for caching, sessions,
# and CRDT state. Cross-region CRDT sync goes through Kafka.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "KEY_PREFIX": f"beacon:{BEACON_REGION}",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_CLASS": "redis.ConnectionPool",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
        },
    },
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.environ.get("REDIS_HOST", "127.0.0.1"), 6379)],
        },
    },
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = "django-db"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ── Kafka (Ch13) — now cross-region ─────────────────────────
# Kafka clusters in each region are connected via MirrorMaker 2.
# The local producer writes to the local cluster; MirrorMaker
# replicates select topics cross-region.
KAFKA_PRODUCER_CONFIG = {
    "bootstrap.servers": os.environ.get("KAFKA_BROKERS", "localhost:9092"),
    "acks": "all",
    "retries": 3,
    "compression.type": "snappy",
    "linger.ms": 5,
    "batch.size": 16384,
}

ELASTICSEARCH_HOSTS = os.environ.get(
    "ELASTICSEARCH_HOSTS", "http://localhost:9200"
).split(",")

FEED_CONFIG = {
    "CELEBRITY_THRESHOLD": 10_000,
    "ACTIVE_WINDOW_DAYS": 30,
    "FEED_MAX_ITEMS": 500,
    "FEED_TTL_SECONDS": 60 * 60 * 24 * 30,
}

# ── ClickHouse Config (Ch12, carried forward) ───────────────
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DB = os.environ.get("CLICKHOUSE_DB", "beacon_analytics")

# ── Iceberg / Trino Config (Ch12, carried forward) ──────────
TRINO_HOST = os.environ.get("TRINO_HOST", "localhost")
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
ICEBERG_CATALOG = os.environ.get("ICEBERG_CATALOG", "beacon")

SERVICE_SECRET = os.environ.get("BEACON_SERVICE_SECRET", "dev-secret-do-not-use-in-production")
PAGE_SERVICE_ADDR = os.environ.get("PAGE_SERVICE_ADDR", "localhost:50051")

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

NEWS_API_KEY = "beacon-dev-api-key-change-in-production"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "beacon.latency": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "beacon.queries": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.cache": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.external": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery.task": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.sharding": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.outbox": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.search-service": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.collab": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.feed": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.analytics": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "beacon.region": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
