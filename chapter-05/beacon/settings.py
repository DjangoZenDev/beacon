"""
Django settings for Beacon v0.5 — Chapter 5: Read Replicas.

Key changes from Chapter 4:
- "replica" database config pointing to a read-only PostgreSQL standby
- DATABASE_ROUTERS configured with ReadReplicaRouter
- Denormalized incoming_count/outgoing_count on Page model
- .only() on PageListView to skip loading the body field
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-beacon-ch5-dev-key-change-in-production"

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

# ── Chapter 5: Multi-Database Configuration ───────────────────────
#
# Django has supported multiple databases since version 1.2. Each
# database gets an alias ("default", "replica") and a connection
# config. The DATABASE_ROUTERS list determines which alias is used
# for each operation.
#
# "default": the primary PostgreSQL server. Handles all writes
#   (INSERT, UPDATE, DELETE) and reads that require strong consistency
#   (e.g., reading your own writes within a transaction).
#
# "replica": a read-only streaming replica. Handles all reads (SELECT)
#   where slight staleness (10-100ms replication lag) is acceptable.
#   The OPTIONS set default_transaction_read_only=on as a safety net
#   to prevent accidental writes to the replica.
#
# pgbouncer sits between Django and both PostgreSQL instances,
# managing separate connection pools for primary and replica.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "192.168.1.10",  # Primary server
        "PORT": "6432",           # pgbouncer
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
        "HOST": "192.168.1.11",  # Replica server
        "PORT": "6432",           # pgbouncer
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            # Prevent accidental writes to the replica.
            # If code tries to write to the replica, PostgreSQL
            # returns an error instead of silently succeeding on
            # a writable standby.
            "options": "-c default_transaction_read_only=on",
        },
    },
}

# ── Chapter 5: Database Router ────────────────────────────────────
#
# ReadReplicaRouter routes all reads to "replica" and all writes to
# "default". Migrations only run on "default".
#
# Important: when a request writes to the database and then reads
# from it within the same request, the read should be served from
# the primary because the replica may not have received the write
# yet. The router handles this via the thread-local
# use_primary_for_request() mechanism.
DATABASE_ROUTERS = [
    "core.db_router.ReadReplicaRouter",
]

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
    },
}
