"""Beacon v0.13 — Ring Manager."""
import json, logging, threading
from .consistent_hash import ConsistentHashRing
logger = logging.getLogger("beacon.sharding")

class RingManager:
    def __init__(self, etcd_host="localhost", etcd_port=2379):
        self.etcd_host = etcd_host; self.etcd_port = etcd_port
        self.client = None; self.ring = ConsistentHashRing()
        self.lock = threading.Lock(); self._loaded = False

    def _get_client(self):
        if self.client is None:
            try:
                import etcd3; self.client = etcd3.client(host=self.etcd_host, port=self.etcd_port)
            except Exception as exc: logger.error("etcd3 unavailable: %s", exc); return None
        return self.client

    def initialize(self, shards=None):
        client = self._get_client()
        if client:
            try: self._load_ring_from_etcd(); self._loaded = True; self._start_watcher(); return
            except Exception as exc: logger.warning("etcd load failed: %s", exc)
        if shards is None:
            from django.conf import settings; shards = list(getattr(settings,"SHARD_MAP",{}).keys())
        if shards:
            with self.lock: self.ring = ConsistentHashRing(shards=shards)
            self._loaded = True

    def _load_ring_from_etcd(self):
        c = self._get_client()
        if c is None: raise RuntimeError("no etcd client")
        value, _ = c.get("/beacon/shards/ring")
        if value is None: raise RuntimeError("no ring config")
        config = json.loads(value)
        with self.lock:
            self.ring = ConsistentHashRing(replicas=config.get("replicas",150))
            for s in config["shards"]: self.ring.add_shard(s["name"])

    def _start_watcher(self):
        def cb(event):
            if event.type == "put":
                try: self._load_ring_from_etcd()
                except Exception: pass
        def loop():
            c = self._get_client()
            if c is None: return
            try:
                for event in c.watch("/beacon/shards/ring"): cb(event)
            except Exception: pass
        threading.Thread(target=loop, daemon=True).start()

    def get_shard(self, key):
        if not self._loaded: raise ValueError("Ring not initialized")
        with self.lock: return self.ring.get_shard(key)

ring_manager = RingManager()
