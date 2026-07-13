"""
Django settings for Beacon v0.6 — Chapter 6: Sharding.

Key changes from Chapter 5:
- SHARD_MAP dict defining 4 shard databases (shard-0 through shard-3)
- DATABASES updated with all shard connection configs
- DATABASE_ROUTERS updated to ["core.sharding.router.OrganizationShardRouter"]
- etcd3 ring manager for consistent hash ring synchronization
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-beacon-ch6-dev-key-change-in-production"

DEBUG = False

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_results",
    "core",
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
]

ROOT_URLCONF = "beacon.urls"

TEMPLATES = [
    {
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
    },
]

WSGI_APPLICATION = "beacon.wsgi.application"

# ── Chapter 6: Sharded Multi-Database Configuration ───────────────
#
# Each shard is an independent PostgreSQL instance holding a subset of
# data partitioned by organization_id. The consistent hash ring maps
# each organization to exactly one shard.
#
# "default" remains as the primary for auth, sessions, and global data
# that does not belong to any single organization.
#
# Shard databases (shard-0 through shard-3) each hold pages/links for
# a subset of organizations. The OrganizationShardRouter routes reads
# and writes to the correct shard based on organization_id.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.10",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "options": "-c search_path=public",
        },
    },
    "replica": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon",
        "USER": "beacon_readonly",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.11",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "options": "-c default_transaction_read_only=on",
        },
    },
}

# ── Chapter 6: Shard Map ──────────────────────────────────────────
#
# Each shard is a separate PostgreSQL database. In production these
# would be on separate machines. The consistent hash ring maps
# organization_id → shard-N alias, and Django uses this dict to
# resolve the alias to a connection config.
SHARD_MAP = {
    "shard-0": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard_0",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.20",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    },
    "shard-1": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard_1",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.21",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    },
    "shard-2": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard_2",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.22",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    },
    "shard-3": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_shard_3",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.23",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    },
}

# Merge shard databases into the main DATABASES dict.
DATABASES.update(SHARD_MAP)

# ── Chapter 6: Database Router ────────────────────────────────────
#
# OrganizationShardRouter replaces ReadReplicaRouter from Chapter 5.
# It combines shard routing (by organization_id) with read-replica
# routing (reads to replica of the correct shard, writes to primary).
DATABASE_ROUTERS = [
    "core.sharding.router.OrganizationShardRouter",
]

# ── Chapter 6: etcd Ring Manager Configuration ────────────────────
#
# The RingManager syncs the consistent hash ring configuration from
# etcd. All application processes share the same ring, so routing is
# consistent across the fleet. When a shard is added or removed, the
# etcd watch callback rebuilds the ring without a restart.
ETCD_HOST = "localhost"
ETCD_PORT = 2379
ETCD_RING_KEY = "/beacon/shards/ring"

# ── Redis Cache Configuration (from Chapter 3) ────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/0",
        "KEY_PREFIX": "beacon",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_CLASS": "redis.ConnectionPool",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "COMPRESSOR_CLASS": "django_redis.compressors.zlib.ZlibCompressor",
            "SERIALIZER_CLASS": "django_redis.serializers.msgpack.MSGPackSerializer",
        },
    },
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ── Celery Configuration (from Chapter 4) ─────────────────────────
CELERY_BROKER_URL = "redis://localhost:6379/1"
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

NEWS_API_KEY = "beacon-dev-api-key-change-in-production"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "beacon.latency": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "beacon.queries": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "beacon.cache": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "beacon.external": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery.task": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "beacon.replication": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "beacon.sharding": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
