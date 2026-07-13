"""
Beacon v0.12 — ClickHouse Kafka Consumer

Consumes "beacon.events.page_views" topic from Kafka and
batch-inserts into ClickHouse for real-time analytics.

Chapter 12, Principle 3: "CDC is the bridge."
  Debezium captures changes from PostgreSQL WAL,
  streams them to Kafka, and this consumer writes to ClickHouse.

The latency from PostgreSQL write to ClickHouse availability
is typically 200-500ms — sufficient for operational analytics.
"""

import json
import logging
import time

logger = logging.getLogger("beacon.analytics")


class ClickHouseIngestor:
    """
    Batch inserts page view events from Kafka into ClickHouse.

    Uses clickhouse-driver for native protocol (faster than HTTP).
    Batches of 1000 rows for optimal throughput.
    """

    def __init__(self, ch_host="localhost", ch_port=9000, ch_db="beacon_analytics"):
        self.ch_host = ch_host
        self.ch_port = ch_port
        self.ch_db = ch_db
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from clickhouse_driver import Client
            self._client = Client(
                host=self.ch_host,
                port=self.ch_port,
                database=self.ch_db,
            )
        return self._client

    def insert_batch(self, batch: list[dict]):
        """
        Insert a batch of page view events into ClickHouse.

        Args:
            batch: List of dicts with keys: event_time, page_id, user_id,
                   duration_seconds, referrer, organization_id,
                   page_title, page_slug, user_username, user_department.
        """
        if not batch:
            return

        try:
            self.client.execute(
                "INSERT INTO beacon_analytics.page_views "
                "(event_time, page_id, user_id, duration_seconds, referrer, "
                "organization_id, page_title, page_slug, user_username, "
                "user_department) VALUES",
                batch,
            )
            logger.debug("Inserted %d page views into ClickHouse", len(batch))
        except Exception as exc:
            logger.error("ClickHouse insert failed: %s", exc)
            raise


def run_clickhouse_consumer():
    """
    Main entry point: consume from Kafka, batch insert into ClickHouse.

    Runs as a long-lived process alongside the main application.
    """
    from kafka import KafkaConsumer

    ingestor = ClickHouseIngestor()

    consumer = KafkaConsumer(
        "beacon.events.page_views",
        bootstrap_servers=["localhost:9092"],
        group_id="clickhouse-ingest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        max_poll_records=1000,
    )

    logger.info("ClickHouse consumer started on beacon.events.page_views")

    batch = []
    batch_size = 1000
    last_flush = time.time()
    flush_interval = 5  # seconds

    for message in consumer:
        try:
            event = message.value
            payload = event.get("payload", {})

            batch.append({
                "event_time": payload.get("viewed_at", payload.get("timestamp")),
                "page_id": payload.get("page_id", 0),
                "user_id": payload.get("user_id", 0),
                "duration_seconds": payload.get("duration_seconds", 0),
                "referrer": payload.get("referrer", ""),
                "organization_id": payload.get("organization_id", 1),
                "page_title": payload.get("page_title", ""),
                "page_slug": payload.get("page_slug", ""),
                "user_username": payload.get("user_username", ""),
                "user_department": payload.get("user_department", "Unknown"),
            })

            # Flush when batch is full or flush interval elapsed.
            if len(batch) >= batch_size or (time.time() - last_flush) > flush_interval:
                ingestor.insert_batch(batch)
                batch = []
                last_flush = time.time()

        except Exception as exc:
            logger.error("ClickHouse consumer error: %s", exc)

    # Final flush.
    if batch:
        ingestor.insert_batch(batch)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_clickhouse_consumer()
