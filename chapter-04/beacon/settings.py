"""
Django settings for Beacon v0.4 — Chapter 4: The Monolith Groans.

Key changes from Chapter 3:
- Celery configuration (broker_url, result_backend, task settings)
- django-celery-results for storing task results in Django's ORM
- Celery task routing with task_acks_late and worker_prefetch_multiplier
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-beacon-ch4-dev-key-change-in-production"

# Chapter 4: DEBUG stays off for realistic profiling.
DEBUG = False

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Chapter 4: Store Celery task results in Django's database.
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
    # Chapter 4: QueryCountMiddleware now logs when >20 queries per
    # request. With Celery, expensive work moves off the critical path,
    # so query counts should drop further from Chapter 3 levels.
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "beacon_ch4",
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

# ── Chapter 4: Celery Configuration ───────────────────────────────
#
# Celery is the background task queue for Beacon. It moves non-critical
# work (notifications, future search indexing, analytics) off the
# synchronous request path. The user who clicks "Save" returns
# immediately; the notification delivery happens later.
#
# Message broker: Redis database 1 (db 0 is for caching).
# Using a separate Redis database isolates task queues from caches,
# preventing a cache flush from accidentally dropping queued tasks.
CELERY_BROKER_URL = "redis://localhost:6379/1"

# Result backend: Django's ORM via django-celery-results.
# Task results are stored as CELERY_RESULT rows in PostgreSQL.
# Admins can inspect task results from the Django admin.
CELERY_RESULT_BACKEND = "django-db"

# Serialization: JSON only. It is the safe, interoperable default.
# Pickle is rejected because it can execute arbitrary code.
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# Timezone: all timestamps in UTC.
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

# Task routing: tasks go to the "default" queue unless specified.
CELERY_TASK_DEFAULT_QUEUE = "default"

# Task execution limits.
# soft_time_limit: the worker raises a SoftTimeLimitExceeded exception,
#   giving the task a chance to clean up.
# time_limit: the worker kills the task process unconditionally.
CELERY_TASK_SOFT_TIME_LIMIT = 300   # 5 minutes
CELERY_TASK_TIME_LIMIT = 600        # 10 minutes hard limit

# Chapter 4: task_acks_late and worker_prefetch_multiplier.
#
# task_acks_late=True: the worker acknowledges a task AFTER it completes,
# not when it receives it. If the worker crashes mid-execution, the
# broker redelivers the task to another worker. This prevents task loss
# at the cost of possible double-delivery (tasks must be idempotent).
CELERY_TASK_ACKS_LATE = True

# worker_prefetch_multiplier=1: each worker reserves only 1 task at a
# time. This is critical for fairness: if one worker gets a slow task,
# other workers are not sitting idle because they pre-fetched work they
# cannot start yet.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Retry on connection loss to the broker at startup.
# Without this, the worker fails to start if Redis is temporarily down.
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ── Chapter 4: External API key (for core/external.py) ────────────
# In production, this comes from an environment variable.
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
    },
}
