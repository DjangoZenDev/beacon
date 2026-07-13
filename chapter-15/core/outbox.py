"Beacon v0.15 — Outbox Pattern."
import json, logging
from django.db import models
logger = logging.getLogger(__name__)

class OutboxMessage(models.Model):
    STATUS_PENDING = "pending"; STATUS_PROCESSING = "processing"; STATUS_SENT = "sent"; STATUS_FAILED = "failed"
    STATUS_CHOICES = [(STATUS_PENDING,"Pending"),(STATUS_PROCESSING,"Processing"),(STATUS_SENT,"Sent"),(STATUS_FAILED,"Failed")]
    topic = models.CharField(max_length=255)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=["status","created_at"], name="outbox_status_created_idx")]
        ordering = ["created_at"]

def enqueue_outbox(topic, payload):
    OutboxMessage.objects.create(topic=topic, payload=payload)
    logger.debug("Outbox enqueued: %s", topic)
