
"""
Beacon v0.8 — Outbox Pattern

Reliable message publication: write messages to the outbox table
within the same database transaction as the business data. A
separate poller process publishes them to Redis/Kafka.

Chapter 8, Principle 2: "Use the outbox pattern for reliable publication.
Never publish to a message broker from inside a database transaction."
"""

import json
import logging

from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class OutboxMessage(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    topic = models.CharField(max_length=255)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"], name="outbox_status_created_idx"),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"OutboxMessage({self.topic}:{self.status})"


def enqueue_outbox(topic: str, payload: dict):
    """Enqueue a message in the outbox within the current transaction."""
    OutboxMessage.objects.create(topic=topic, payload=payload)
    logger.debug("Outbox enqueued: %s -> %s", topic, json.dumps(payload)[:200])
