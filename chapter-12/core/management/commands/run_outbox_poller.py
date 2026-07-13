"Beacon v0.12 — Run outbox poller management command."
import time, json, logging
from django.core.management.base import BaseCommand
from core.outbox import OutboxMessage
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Poll the outbox table and publish messages to Kafka"

    def handle(self, *args, **options):
        self.stdout.write("Starting outbox poller...")
        while True:
            messages = OutboxMessage.objects.filter(status=OutboxMessage.STATUS_PENDING).order_by("created_at")[:50]
            for msg in messages:
                msg.status = OutboxMessage.STATUS_PROCESSING
                msg.save()
                try:
                    # In a real system, publish to Kafka here
                    msg.status = OutboxMessage.STATUS_SENT
                    msg.processed_at = timezone.now()
                    msg.save()
                except Exception as exc:
                    msg.retry_count += 1
                    if msg.retry_count >= msg.max_retries:
                        msg.status = OutboxMessage.STATUS_FAILED
                        msg.last_error = str(exc)
                    else:
                        msg.status = OutboxMessage.STATUS_PENDING
                    msg.save()
                    logger.error("Outbox publish failed: %s", exc)
            time.sleep(1)
