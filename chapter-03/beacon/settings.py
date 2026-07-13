"""
Django settings for Beacon v0.3 — Chapter 3: Caching Everything That Moves.

Key changes from Chapter 2:
- Redis cache backend (django-redis) replaces no-cache approach
- CACHES config with KEY_PREFIX="beacon"
- Redis connection pool for Django's cache framework
- Write-invalidate pattern: cache.delete() on every Page.save()
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-beacon-ch3-dev-key-change-in-production"

# Chapter 3: Still DEBUG=False for realistic profiling, but we now
# have Redis caching in front of PostgreSQL so the database sees far
# fewer queries regardless.
DEBUG = False

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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

# Chapter 3: PostgreSQL with pgbouncer (unchanged from Chapter 2).
#
# PostgreSQL handles concurrent reads and writes through MVCC.
# pgbouncer manages a pool of persistent connections on port 6432.
# CONN_MAX_AGE=600 keeps connections alive for 10 minutes.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_ch3",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "localhost",
        "PORT": "6432",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "options": "-c search_path=public",
        },
    },
}

# ── Chapter 3: Redis Cache Configuration ──────────────────────────
#
# django-redis provides a Redis-backed cache backend for Django.
# It uses a connection pool (default 10 connections) and supports
# the full Django cache API: get, set, delete, incr, touch, etc.
#
# KEY_PREFIX="beacon" namespaces all cache keys. This prevents
# collisions if Redis is shared with other applications.
#
# The TIMEOUT default of 300 seconds means cached entries live for
# 5 minutes unless explicitly overridden. This strikes the balance
# between freshness (users see recent edits quickly) and hit ratio
# (longer TTL means more cache hits).
#
# OPTIONS:
#   - PARSER_CLASS: use the msgpack parser for faster serialization
#     than pickle but safer than raw pickle
#   - CONNECTION_POOL_CLASS: use a connection pool to avoid opening
#     a new TCP connection on every cache operation
#   - COMPRESSOR_CLASS: zlib compression for values > 1KB
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

# Chapter 3: Session cache.
# Store Django sessions in Redis instead of the database. This
# removes the session table from the write path entirely and
# reduces the number of database round-trips per request.
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

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
    },
}
