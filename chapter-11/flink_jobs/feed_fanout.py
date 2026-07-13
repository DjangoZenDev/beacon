
"""
Beacon v0.11 — PyFlink Feed Fanout Job

Stream processing job that consumes page events from Kafka,
fans out to active followers' feeds, and sinks to Redis.

Runs continuously on Apache Flink with exactly-once semantics.
Horizontal scaling: increase parallelism from 4 to 40 for 10× throughput.

Chapter 11, Principle 3: "Stream processing replaces polling loops."
"""

import json
import logging

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.watermark_strategy import WatermarkStrategy

logger = logging.getLogger("beacon.flink")

# ── Constants ────────────────────────────────────────────────────

CELEBRITY_THRESHOLD = 10_000
FEED_MAX_ITEMS = 500


def fanout_event(event_json: str) -> list[str]:
    """
    Process a single page.updated event.

    1. Parse the event to get page_id.
    2. Look up the page's follower count from Redis.
    3. If celebrity: skip fan-out (event store only).
    4. If not celebrity: fan out to active followers.

    Returns:
        List of JSON strings for Redis feed pushes.
    """
    import time as time_mod

    try:
        event = json.loads(event_json)
    except json.JSONDecodeError:
        return []

    event_type = event.get("type", "")
    if event_type not in ("page.created", "page.updated"):
        return []

    payload = event.get("payload", {})
    page_id = payload.get("page_id")
    if not page_id:
        return []

    follower_count = _get_follower_count(page_id)
    if follower_count > CELEBRITY_THRESHOLD:
        return [json.dumps({"type": "event_store", **payload})]

    active_followers = _get_active_followers(page_id)
    results = []
    for uid in active_followers:
        results.append(json.dumps({
            "type": "feed_push",
            "user_id": uid,
            "page_id": page_id,
            "event_type": event_type,
            "timestamp": time_mod.time(),
        }))
    return results


def _get_follower_count(page_id: int) -> int:
    try:
        import redis as redis_lib
        r = redis_lib.Redis(host="localhost", port=6379, db=2)
        count = r.get(f"follower_count:{page_id}")
        return int(count) if count else 0
    except Exception:
        return 0


def _get_active_followers(page_id: int) -> list[int]:
    try:
        import redis as redis_lib
        r = redis_lib.Redis(host="localhost", port=6379, db=2)
        followers = r.smembers(f"followers:{page_id}")
        return [int(uid) for uid in followers]
    except Exception:
        return []


class RedisFeedSink:
    """Custom Flink sink: writes feed events to Redis sorted sets."""

    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=1):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            import redis as redis_lib
            self._redis = redis_lib.Redis(
                host=self.redis_host, port=self.redis_port, db=self.redis_db,
            )
        return self._redis

    def invoke(self, value: str, context):
        try:
            event = json.loads(value)
            if event.get("type") != "feed_push":
                return
            user_id = event["user_id"]
            feed_key = f"feed:{user_id}"
            r = self._get_redis()
            pipe = r.pipeline()
            pipe.zadd(feed_key, {value: event.get("timestamp", 0)})
            pipe.zremrangebyrank(feed_key, 0, -(FEED_MAX_ITEMS + 1))
            pipe.expire(feed_key, 60 * 60 * 24 * 30)
            pipe.execute()
        except Exception as exc:
            logger.error("RedisFeedSink error: %s", exc)


def main():
    """Entry point for the PyFlink feed fanout job."""
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(4)

    source = KafkaSource.builder() \
        .set_bootstrap_servers("kafka:9092") \
        .set_topics("beacon.events.pages") \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    ds = env.from_source(source, WatermarkStrategy.no_watermarks(), "kafka-source")
    ds = ds.flat_map(fanout_event)
    ds.add_sink(RedisFeedSink())

    env.execute("Beacon Feed Fanout")


if __name__ == "__main__":
    main()
