
"""
Django settings for Beacon v0.7 — Chapter 7: The Monolith Becomes a Service.

Key changes from Chapter 6:
- djangorestframework added to INSTALLED_APPS
- REST_FRAMEWORK config with pagination and auth
- SERVICE_SECRET for inter-service HMAC auth
- PAGE_SERVICE_ADDR for gRPC client connections
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-beacon-ch7-dev-key-change-in-production"

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
    "rest_framework",   # Chapter 7: DRF for REST API
    "channels",          # Chapter 7: WebSocket support for collab
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

# ── Chapter 7: ASGI for WebSocket/channels ─────────────────────
ASGI_APPLICATION = "beacon.asgi.application"

# ── Chapter 6: Shard Database Configuration ────────────────────
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

DATABASES.update(SHARD_MAP)

DATABASE_ROUTERS = [
    "core.sharding.router.OrganizationShardRouter",
]

# ── Redis Cache Configuration ──────────────────────────────────
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

# ── Chapter 7: Channels layer (Redis) ──────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

# ── Celery Configuration (from Chapter 4) ──────────────────────
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

# ── Chapter 7: Inter-service authentication ────────────────────
SERVICE_SECRET = "dev-secret-do-not-use-in-production"

# ── Chapter 7: gRPC service addresses ──────────────────────────
PAGE_SERVICE_ADDR = "localhost:50051"
SEARCH_SERVICE_ADDR = "localhost:50052"
NOTIFY_SERVICE_ADDR = "localhost:50053"
COLLAB_SERVICE_ADDR = "localhost:50054"

# ── Chapter 7: DRF Configuration ───────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
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
        "beacon.sharding": {
            "handlers": ["console"],
            "level": "INFO",
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
