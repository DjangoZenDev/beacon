
"""Beacon v0.13 — Search Service: Kafka Consumer."""
import json, logging
from kafka import KafkaConsumer
logger = logging.getLogger("beacon.search-service")

class PageIndexer:
    def __init__(self, es_url="http://localhost:9200"): self.es_url = es_url
    def index_page(self, page_data): logger.info("Indexing page %s: %s", page_data.get("id"), page_data.get("title"))
    def delete_page(self, page_id): logger.info("Deleting page %s from index", page_id)
    def handle_event(self, event_type, payload):
        if event_type in ("page.created","page.updated"): self.index_page(payload)
        elif event_type == "page.deleted": self.delete_page(payload.get("page_id",0))

def main():
    indexer = PageIndexer()
    consumer = KafkaConsumer("beacon.events.pages", bootstrap_servers=["localhost:9092"], group_id="search-service", value_deserializer=lambda v: json.loads(v.decode("utf-8")), auto_offset_reset="earliest", enable_auto_commit=True)
    logger.info("Search service consumer started on beacon.events.pages")
    for message in consumer:
        try:
            payload = message.value; event_type = payload.get("type","unknown")
            indexer.handle_event(event_type, payload.get("payload",{}))
        except Exception as exc: logger.error("Failed to process event: %s", exc)

if __name__ == "__main__": logging.basicConfig(level=logging.INFO); main()
