"""
Django settings for Beacon v0.12 — Data Lakes and the Analytical Sidecar.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("SECRET_KEY", "beacon-dev-key-ch12")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","channels","django_celery_results",
    "core","analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.LatencyMiddleware",
]

ROOT_URLCONF = "beacon.urls"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "beacon.wsgi.application"
ASGI_APPLICATION = "beacon.asgi.application"

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

# ClickHouse for analytics
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST","localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT","9000"))
CLICKHOUSE_DB = os.environ.get("CLICKHOUSE_DB","beacon_analytics")

# Redis / Celery
CELERY_BROKER_URL = os.environ.get("REDIS_URL","redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

# Channels
CHANNEL_LAYERS = {"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[os.environ.get("REDIS_URL","redis://localhost:6379/0")]}}}

# Kafka for analytics pipeline
KAFKA_BROKERS = os.environ.get("KAFKA_BROKERS","localhost:9092")

# Sharding
SHARD_MAP = {}
CACHE_MIDDLEWARE_SECONDS = 300

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL","redis://localhost:6379/1"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
NEWS_API_KEY = os.environ.get("NEWS_API_KEY","")
