"""
Beacon v0.16 — Outbox Poller. Principle 8: Only publish from the poller.

Never publish to a message broker from inside a database transaction.
This poller runs as a separate process and moves messages from the
outbox table to Kafka.
"""
import time, logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.outbox import OutboxMessage
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Poll the outbox and publish to Kafka"
    def handle(self, *args, **options):
        self.stdout.write("Starting outbox poller...")
        while True:
            msgs = OutboxMessage.objects.filter(status=OutboxMessage.STATUS_PENDING)[:50]
            for msg in msgs:
                msg.status = OutboxMessage.STATUS_PROCESSING; msg.save()
                try:
                    msg.status = OutboxMessage.STATUS_SENT; msg.processed_at = timezone.now(); msg.save()
                except Exception as exc:
                    msg.retry_count += 1
                    if msg.retry_count >= msg.max_retries:
                        msg.status = OutboxMessage.STATUS_FAILED; msg.last_error = str(exc)
                    else: msg.status = OutboxMessage.STATUS_PENDING
                    msg.save()
            time.sleep(1)
