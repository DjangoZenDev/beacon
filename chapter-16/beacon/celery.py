"""Beacon v0.16 — Celery. Principle 4: Async work off the critical path."""
import os
from celery import Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "beacon.settings")
app = Celery("beacon")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Celery worker is alive: {self.request.id}")
