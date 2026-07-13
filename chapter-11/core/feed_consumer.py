"""
Beacon v0.11 — Feed Consumer (Kafka)

Consumes "beacon.events.pages" topic and calls FeedManager.fanout_on_write()
for active followers. This runs as a separate process alongside the main app.

Chapter 11, Principle 3: "Stream processing replaces polling loops."
"""

import json
import logging

from kafka import KafkaConsumer

logger = logging.getLogger("beacon.feed")


class FeedEventConsumer:
    """
    Consumes page events from Kafka and fans out to active followers.
    """

    def __init__(self, kafka_brokers=None):
        self.kafka_brokers = kafka_brokers or ["localhost:9092"]

    def handle_event(self, event_type: str, payload: dict):
        """
        Process a single page event.

        For page.created and page.updated: fan out to active followers.
        For page.deleted: no fan-out (event will expire naturally).
        """
        if event_type not in ("page.created", "page.updated"):
            return

        from core.models import Page
        from core.feed import feed_manager

        page_id = payload.get("page_id")
        if not page_id:
            return

        try:
            page = Page.objects.get(pk=page_id)
        except Page.DoesNotExist:
            logger.warning("Feed consumer: page %s not found", page_id)
            return

        # Celebrity check: skip fan-out for popular pages.
        if page.incoming_count > feed_manager.CELEBRITY_THRESHOLD:
            logger.info(
                "Skipping fan-out for celebrity page %s (%d followers)",
                page_id, page.incoming_count,
            )
            return

        # Get active followers (last active within ACTIVE_WINDOW_DAYS).
        from datetime import timedelta
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=feed_manager.ACTIVE_WINDOW_DAYS)

        # In production, this would be a more efficient query using
        # a follow/friendship model. Here we fan-out to all users
        # in the same organization who were recently active.
        from django.contrib.auth import get_user_model
        User = get_user_model()

        active_followers = User.objects.filter(
            last_login__gte=cutoff,
        ).values_list("id", flat=True)

        follower_ids = list(active_followers)
        if follower_ids:
            feed_manager.fanout_on_write(page, event_type, follower_ids)


def run_feed_consumer():
    """Run the feed fan-out consumer."""
    consumer = FeedEventConsumer()

    kafka_consumer = KafkaConsumer(
        "beacon.events.pages",
        bootstrap_servers=consumer.kafka_brokers,
        group_id="feed-fanout",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    logger.info("Feed consumer started on beacon.events.pages")

    for message in kafka_consumer:
        try:
            payload = message.value
            event_type = payload.get("type", "unknown")
            consumer.handle_event(event_type, payload.get("payload", {}))
        except Exception as exc:
            logger.error("Feed consumer error: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_feed_consumer()
