"""
Beacon v0.10 — Search Indexer (Kafka Consumer)

Consumes page events from the "beacon.events.pages" Kafka topic
and bulk-indexes documents into Elasticsearch via PageDocument.

This is the C in CQRS: the search index is a read model, updated
asynchronously from the write model (PostgreSQL). The search index
may be up to refresh_interval (1s) behind the database.

Chapter 10, Principle 4: "Indexing is write-time computation."
"""

import json
import logging

from kafka import KafkaConsumer

logger = logging.getLogger("beacon.search-service")


class SearchIndexer:
    """
    Consumes page events from Kafka and indexes into Elasticsearch.

    Uses elasticsearch-dsl's PageDocument for mapping and
    elasticsearch.helpers.bulk for efficient batch indexing.
    """

    def __init__(self, es_hosts=None, kafka_brokers=None):
        self.es_hosts = es_hosts or ["http://localhost:9200"]
        self.kafka_brokers = kafka_brokers or ["localhost:9092"]

    def index_page(self, page):
        """
        Convert a Django Page to a PageDocument and save to Elasticsearch.

        Args:
            page: A core.models.Page instance.
        """
        from core.search import PageDocument

        doc = PageDocument.from_page(page)
        doc.save(refresh=False)  # refresh=False for bulk throughput.
        logger.debug("Indexed page %s: %s", page.pk, page.title)

    def delete_page(self, page_id: int):
        """
        Remove a page from the Elasticsearch index.

        Args:
            page_id: The primary key of the deleted page.
        """
        from core.search import PageDocument

        try:
            doc = PageDocument.get(id=page_id)
            doc.delete()
            logger.debug("Deleted page %s from index", page_id)
        except Exception as exc:
            logger.warning("Failed to delete page %s: %s", page_id, exc)

    def handle_event(self, event_type: str, payload: dict):
        """
        Dispatch a Kafka event to the appropriate handler.

        Args:
            event_type: "page.created", "page.updated", or "page.deleted".
            payload: Event payload with page_id etc.
        """
        from core.models import Page

        page_id = payload.get("page_id")

        if event_type in ("page.created", "page.updated"):
            try:
                page = Page.objects.get(pk=page_id)
                self.index_page(page)
            except Page.DoesNotExist:
                self.delete_page(page_id)
        elif event_type == "page.deleted":
            self.delete_page(page_id)
        else:
            logger.debug("Ignoring unknown event type: %s", event_type)


def run_indexer():
    """
    Run the search indexer consumer.

    Connects to Kafka, consumes page events, and indexes into Elasticsearch.
    Designed for long-running operation as a service process.
    """
    indexer = SearchIndexer()

    consumer = KafkaConsumer(
        "beacon.events.pages",
        bootstrap_servers=indexer.kafka_brokers,
        group_id="search-indexer",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    logger.info(
        "Search indexer started on beacon.events.pages "
        "(es=%s, kafka=%s)",
        indexer.es_hosts, indexer.kafka_brokers,
    )

    for message in consumer:
        try:
            payload = message.value
            event_type = payload.get("type", "unknown")
            indexer.handle_event(event_type, payload.get("payload", {}))
        except Exception as exc:
            logger.error("Failed to process index event: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_indexer()
