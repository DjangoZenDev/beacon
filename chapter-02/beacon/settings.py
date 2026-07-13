"""
Django settings for Beacon v0.2 — Chapter 2: The First Thousand Users.

Key changes from Chapter 1:
- PostgreSQL replaces SQLite (more connections, real concurrency)
- pgbouncer connection pooler (session pooling mode)
- CONN_MAX_AGE for persistent connections
- DEBUG=False for realistic profiling
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-beacon-ch2-dev-key-change-in-production"

# Chapter 2: Turn off DEBUG for realistic profiling.
# Django captures every SQL query in memory when DEBUG=True, which
# distorts performance measurements. Our load tests run against a
# production-configured server.
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
    # Chapter 2: Query count middleware for development profiling.
    # Removed in production — adds ~1ms overhead per request.
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

# Chapter 2: PostgreSQL replaces SQLite.
#
# SQLite was the right choice for Chapter 1: zero-config, reliable,
# fast enough for 10 users. But SQLite serializes all writes through a
# single lock — at 50+ concurrent users, writes queue up and reads
# behind them time out. PostgreSQL handles concurrent reads and writes
# natively through MVCC (Multiversion Concurrency Control).
#
# pgbouncer sits between Django and PostgreSQL, managing a pool of
# persistent connections. Django opens connections to pgbouncer on
# localhost:6432; pgbouncer opens connections to PostgreSQL on
# localhost:5432 and reuses them across requests.
#
# Without pgbouncer, each of gunicorn's 9 workers would open its own
# PostgreSQL connection, plus Django's ORM would open extra connections
# for background tasks — easily exceeding PostgreSQL's default
# max_connections of 100. With pgbouncer, a pool of ~20 connections
# serves all workers.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_ch2",
        "USER": "beacon",
        "PASSWORD": "beacon_dev_password",
        "HOST": "localhost",      # pgbouncer is on 6432
        "PORT": "6432",
        "CONN_MAX_AGE": 600,      # Keep connections alive for 10 minutes.
        "CONN_HEALTH_CHECKS": True,  # Verify connection before using it.
        "OPTIONS": {
            # Use server-side binding to reduce preparation overhead.
            "options": "-c search_path=public",
        },
    },
}

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

# Chapter 2: Logging configuration for profiling.
# SQL queries with duration > 50ms are logged at WARNING level.
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
            "level": "WARNING",  # Only log slow queries.
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
    },
}
