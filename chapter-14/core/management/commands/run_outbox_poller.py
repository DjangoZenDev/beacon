
"""Beacon v0.14 — Outbox Poller."""
import json, logging, time
from django.core.management.base import BaseCommand; from django.db import transaction; from django.utils import timezone
logger = logging.getLogger("beacon.outbox")
class Command(BaseCommand):
    help = "Poll the outbox and publish messages to Kafka/Redis."
    def add_arguments(self, parser): parser.add_argument("--batch-size", type=int, default=50); parser.add_argument("--sleep", type=float, default=0.5); parser.add_argument("--broker", choices=["redis","kafka"], default="kafka")
    def handle(self, *args, **options):
        batch_size = options["batch_size"]; sleep_secs = options["sleep"]; broker = options["broker"]
        self.stdout.write(f"Outbox poller starting (broker={broker}, batch={batch_size})")
        while True:
            count = self._poll_and_publish(batch_size, broker)
            if count == 0: time.sleep(sleep_secs)
    def _poll_and_publish(self, batch_size, broker):
        from core.outbox import OutboxMessage
        with transaction.atomic():
            messages = list(OutboxMessage.objects.select_for_update(skip_locked=True).filter(status=OutboxMessage.STATUS_PENDING).order_by("created_at")[:batch_size])
            if not messages: return 0
            ids = [m.pk for m in messages]; OutboxMessage.objects.filter(pk__in=ids).update(status=OutboxMessage.STATUS_PROCESSING)
        for msg in messages:
            try: self._publish(msg, broker); OutboxMessage.objects.filter(pk=msg.pk).update(status=OutboxMessage.STATUS_SENT, processed_at=timezone.now())
            except Exception as exc:
                msg.refresh_from_db(); nr = msg.retry_count + 1
                if nr >= msg.max_retries: OutboxMessage.objects.filter(pk=msg.pk).update(status=OutboxMessage.STATUS_FAILED, last_error=str(exc), retry_count=nr); logger.error("Outbox msg %s FAILED: %s", msg.pk, exc)
                else: OutboxMessage.objects.filter(pk=msg.pk).update(status=OutboxMessage.STATUS_PENDING, last_error=str(exc), retry_count=nr); logger.warning("Outbox msg %s retry %d: %s", msg.pk, nr, exc)
        return len(messages)
    def _publish(self, msg, broker):
        if broker == "kafka": self._publish_kafka(msg)
        else: self._publish_redis(msg)
    def _publish_kafka(self, msg):
        try:
            from kafka import KafkaProducer
            producer = KafkaProducer(bootstrap_servers=["localhost:9092"], value_serializer=lambda v: json.dumps(v).encode("utf-8")); producer.send(msg.topic, msg.payload); producer.flush()
        except ImportError: logger.info("Would publish: topic=%s", msg.topic)
    def _publish_redis(self, msg):
        try:
            import redis; r = redis.Redis(host="localhost", port=6379, db=1); r.publish(msg.topic, json.dumps(msg.payload))
        except ImportError: logger.info("Would publish: topic=%s", msg.topic)
