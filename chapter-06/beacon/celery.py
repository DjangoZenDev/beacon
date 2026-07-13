
"""
Beacon v0.6 — Celery Application Configuration

Unchanged from Chapter 5.
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "beacon.settings")

app = Celery("beacon")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """A no-op task used to verify the Celery worker is running."""
    print(f"Celery worker is alive: {self.request.id}")
