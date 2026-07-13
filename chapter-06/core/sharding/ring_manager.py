"""
Beacon v0.6 — Ring Manager (etcd3-backed)

RingManager keeps the consistent hash ring synchronized across all
Beacon application processes via etcd3. It loads the ring configuration
from etcd at startup and watches for changes in real time.

When Maya adds a new shard, she updates the JSON configuration in etcd.
Within seconds, every Beacon process rebuilds its local ring — no restarts,
no deployment, no downtime.

Architecture:
    etcd:/beacon/shards/ring  ←  single source of truth
           │
    ┌──────┼──────┬──────────┐
    ▼      ▼      ▼          ▼
  proc1  proc2  proc3  ...  procN
  (each has a ConsistentHashRing rebuilt on config change)

Chapter 6, Section 6.9: "etcd is essential infrastructure once you have
multiple database instances. The ring configuration must be a single
source of truth."
"""

import json
import logging
import threading

from .consistent_hash import ConsistentHashRing

logger = logging.getLogger("beacon.sharding")


class RingManager:
    """
    Manages the consistent hash ring, synced via etcd3.

    Singleton-like: instantiated once at import time as `ring_manager`.
    All router calls use ring_manager.get_shard() for O(log N) lookups.

    The ring is protected by a threading.Lock, so concurrent shard lookups
    are safe even during a ring rebuild triggered by an etcd watch event.
    """

    def __init__(self, etcd_host="localhost", etcd_port=2379):
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port
        self.client = None
        self.ring = ConsistentHashRing()
        self.lock = threading.Lock()
        self._loaded = False

    def _get_client(self):
        """Lazily create the etcd3 client."""
        if self.client is None:
            try:
                import etcd3
                self.client = etcd3.client(host=self.etcd_host, port=self.etcd_port)
                logger.info(
                    "Connected to etcd3 at %s:%s", self.etcd_host, self.etcd_port,
                )
            except ImportError:
                logger.error("etcd3 package not installed — ring will use defaults.")
                return None
            except Exception as exc:
                logger.error("Failed to connect to etcd3: %s", exc)
                return None
        return self.client

    def initialize(self, shards=None):
        """
        Initialize the ring. Called once at startup.

        If an etcd3 client is available, loads configuration from
        /beacon/shards/ring and starts the watch loop. Otherwise,
        builds the ring from the provided shards list or the
        SHARD_MAP in Django settings.

        Args:
            shards: Optional list of shard names for fallback initialization.
        """
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

        # Fallback: build ring from shards argument or Django settings.
        if shards is None:
            from django.conf import settings
            shards = list(getattr(settings, "SHARD_MAP", {}).keys())

        if shards:
            with self.lock:
                self.ring = ConsistentHashRing(shards=shards)
            self._loaded = True
            logger.info("Ring initialized from settings with %d shards: %s",
                         self.ring.shard_count, shards)
        else:
            logger.warning("No shards configured — ring is empty.")

    def _load_ring_from_etcd(self):
        """Load the ring configuration from etcd."""
        client = self._get_client()
        if client is None:
            raise RuntimeError("etcd3 client is not available.")

        value, _ = client.get("/beacon/shards/ring")
        if value is None:
            raise RuntimeError("No ring configuration found in etcd at /beacon/shards/ring.")

        config = json.loads(value)
        replicas = config.get("replicas", 150)

        with self.lock:
            self.ring = ConsistentHashRing(replicas=replicas)
            for shard in config["shards"]:
                self.ring.add_shard(shard["name"])

        logger.debug(
            "Loaded ring from etcd: %d shards, %d replicas (version %s)",
            self.ring.shard_count,
            replicas,
            config.get("version", "unknown"),
        )

    def _start_watcher(self):
        """
        Watch etcd for changes to /beacon/shards/ring.

        Runs in a daemon thread. When a change is detected, reloads
        the ring configuration. This ensures all processes stay in
        sync without restarts.
        """

        def watch_callback(event):
            if event.type == "put":
                logger.info("Ring configuration changed in etcd — reloading.")
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
        logger.info("Started etcd watch thread for /beacon/shards/ring")

    def get_shard(self, key: int) -> str:
        """
        Get the shard for a key using the current ring.

        Thread-safe. Returns the shard database alias (e.g., "shard-2").

        Args:
            key: The shard key, typically an organization_id.

        Returns:
            The shard name.

        Raises:
            ValueError: If the ring has not been initialized.
        """
        if not self._loaded:
            raise ValueError(
                "Ring not initialized. Call ring_manager.initialize() at startup."
            )

        with self.lock:
            return self.ring.get_shard(key)


# ── Module-level singleton ───────────────────────────────────────
# Imported by router.py and management commands. Initialized once
# at Django startup via the AppConfig.ready() hook.
ring_manager = RingManager()
