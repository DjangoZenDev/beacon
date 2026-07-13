"""
Django settings for Beacon v0.15 — The Cost of Scale.
Adds CDN, cost-tracking, and FinOps instrumentation.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("SECRET_KEY", "beacon-dev-key-ch15")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","channels","django_celery_results","django_prometheus",
    "storages",
    "core","analytics",
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

# CDN-backed static/media storage (Chapter 15)
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME","beacon-assets")
    AWS_S3_REGION_NAME = os.environ.get("AWS_REGION","us-east-1")
    AWS_CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN","")

# Redis / Celery
CELERY_BROKER_URL = os.environ.get("REDIS_URL","redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

# Channels
CHANNEL_LAYERS = {"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[os.environ.get("REDIS_URL","redis://localhost:6379/0")]}}}

# Cache
CACHES = {"default":{"BACKEND":"django.core.cache.backends.redis.RedisCache","LOCATION":os.environ.get("REDIS_URL","redis://localhost:6379/1")}}

# CDN (Chapter 15)
CDN_ENABLED = os.environ.get("CDN_ENABLED", "false").lower() == "true"
CDN_BASE_URL = os.environ.get("CDN_BASE_URL", "")

# OpenTelemetry (Chapter 14 carry-forward)
OTEL_EXPORTER_JAEGER_AGENT_HOST = os.environ.get("JAEGER_HOST","localhost")
OTEL_EXPORTER_JAEGER_AGENT_PORT = int(os.environ.get("JAEGER_PORT","6831"))

# Sharding
SHARD_MAP = {}
CACHE_MIDDLEWARE_SECONDS = 300

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
NEWS_API_KEY = os.environ.get("NEWS_API_KEY","")
