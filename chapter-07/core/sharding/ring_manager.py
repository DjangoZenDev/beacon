"""
Beacon v0.7 — Ring Manager (etcd3-backed)

Carried forward from Chapter 6.
"""
import json, logging, threading
from .consistent_hash import ConsistentHashRing
logger = logging.getLogger("beacon.sharding")


class RingManager:
    def __init__(self, etcd_host="localhost", etcd_port=2379):
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port
        self.client = None
        self.ring = ConsistentHashRing()
        self.lock = threading.Lock()
        self._loaded = False

    def _get_client(self):
        if self.client is None:
            try:
                import etcd3
                self.client = etcd3.client(host=self.etcd_host, port=self.etcd_port)
                logger.info("Connected to etcd3 at %s:%s", self.etcd_host, self.etcd_port)
            except ImportError:
                logger.error("etcd3 package not installed")
                return None
            except Exception as exc:
                logger.error("Failed to connect to etcd3: %s", exc)
                return None
        return self.client

    def initialize(self, shards=None):
        client = self._get_client()
        if client is not None:
            try:
                self._load_ring_from_etcd()
                self._loaded = True
                self._start_watcher()
                logger.info("Ring initialized from etcd3 with %d shards", self.ring.shard_count)
                return
            except Exception as exc:
                logger.warning("Could not load ring from etcd3: %s. Using fallback.", exc)
        if shards is None:
            from django.conf import settings
            shards = list(getattr(settings, "SHARD_MAP", {}).keys())
        if shards:
            with self.lock:
                self.ring = ConsistentHashRing(shards=shards)
            self._loaded = True
            logger.info("Ring initialized from settings with %d shards: %s", self.ring.shard_count, shards)
        else:
            logger.warning("No shards configured — ring is empty.")

    def _load_ring_from_etcd(self):
        client = self._get_client()
        if client is None:
            raise RuntimeError("etcd3 client not available")
        value, _ = client.get("/beacon/shards/ring")
        if value is None:
            raise RuntimeError("No ring config in etcd")
        config = json.loads(value)
        replicas = config.get("replicas", 150)
        with self.lock:
            self.ring = ConsistentHashRing(replicas=replicas)
            for shard in config["shards"]:
                self.ring.add_shard(shard["name"])

    def _start_watcher(self):
        def watch_callback(event):
            if event.type == "put":
                logger.info("Ring config changed — reloading")
                try:
                    self._load_ring_from_etcd()
                    logger.info("Ring reloaded: %d shards", self.ring.shard_count)
                except Exception as exc:
                    logger.error("Failed to reload ring: %s", exc)

        def watch_loop():
            client = self._get_client()
            if client is None:
                return
            try:
                events = client.watch("/beacon/shards/ring")
                for event in events:
                    watch_callback(event)
            except Exception as exc:
                logger.error("etcd watch loop failed: %s", exc)

        thread = threading.Thread(target=watch_loop, daemon=True, name="etcd-ring-watcher")
        thread.start()
        logger.info("Started etcd watch thread")

    def get_shard(self, key: int) -> str:
        if not self._loaded:
            raise ValueError("Ring not initialized")
        with self.lock:
            return self.ring.get_shard(key)


ring_manager = RingManager()
