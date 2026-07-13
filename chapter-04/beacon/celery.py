"""
Beacon v0.4 — Celery Application Configuration

Celery is the background task queue for Beacon. It moves non-critical
work — notifications, future search indexing, analytics — off the
synchronous request path.

The Celery worker is started separately from Django:
    celery -A beacon worker -l info

Architecture:
- Message broker: Redis (db 1), the same instance used for caching (db 0).
- Result backend: Django's ORM via django-celery-results.
- Task modules are auto-discovered from all INSTALLED_APPS that have
  a tasks.py file.
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "beacon.settings")

app = Celery("beacon")

# Load configuration from Django settings under the CELERY_ namespace.
# e.g., CELERY_BROKER_URL in settings.py becomes broker_url.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps.
# Any file named tasks.py in an installed app is automatically loaded.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """A no-op task used to verify the Celery worker is running.

    Usage:
        from beacon.celery import debug_task
        debug_task.delay()
    """
    print(f"Celery worker is alive: {self.request.id}")
