
"""
Beacon v0.13 — Search Indexer (Kafka Consumer)

Consumes page events from the "beacon.events.pages" Kafka topic
and bulk-indexes documents into Elasticsearch via PageDocument.

Chapter 10, Principle 4: "Indexing is write-time computation."
Carried forward through Chapter 13: multi-region search runs per-region.
"""

import json, logging
from kafka import KafkaConsumer
logger = logging.getLogger("beacon.search-service")


class SearchIndexer:
    def __init__(self, es_hosts=None, kafka_brokers=None):
        self.es_hosts = es_hosts or ["http://localhost:9200"]
        self.kafka_brokers = kafka_brokers or ["localhost:9092"]

    def index_page(self, page):
        from core.search import PageDocument
        doc = PageDocument.from_page(page)
        doc.save(refresh=False)
        logger.debug("Indexed page %s: %s", page.pk, page.title)

    def delete_page(self, page_id: int):
        from core.search import PageDocument
        try:
            doc = PageDocument.get(id=page_id)
            doc.delete()
            logger.debug("Deleted page %s from index", page_id)
        except Exception as exc:
            logger.warning("Failed to delete page %s: %s", page_id, exc)

    def handle_event(self, event_type: str, payload: dict):
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
    indexer = SearchIndexer()
    consumer = KafkaConsumer(
        "beacon.events.pages",
        bootstrap_servers=indexer.kafka_brokers,
        group_id="search-indexer",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    logger.info("Search indexer started on beacon.events.pages (es=%s, kafka=%s)", indexer.es_hosts, indexer.kafka_brokers)
    for message in consumer:
        try:
            payload = message.value
            event_type = payload.get("type", "unknown")
            indexer.handle_event(event_type, payload.get("payload", {}))
        except Exception as exc:
            logger.error("Failed to process index event: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_indexer()
