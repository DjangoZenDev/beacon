
"""Beacon v0.9 — Consistent Hash Ring (carried from Ch6)."""
import hashlib, bisect

class ConsistentHashRing:
    def __init__(self, shards=None, replicas=150):
        self.replicas = replicas
        self._ring = {}
        self._sorted_keys = []
        if shards:
            for s in shards:
                self.add_shard(s)

    def _hash(self, key):
        return int(hashlib.md5(str(key).encode()).hexdigest()[:8], 16)

    def add_shard(self, name):
        for i in range(self.replicas):
            pos = self._hash(f"{name}:{i}")
            self._ring[pos] = name
            bisect.insort(self._sorted_keys, pos)

    def remove_shard(self, name):
        for i in range(self.replicas):
            pos = self._hash(f"{name}:{i}")
            if pos in self._ring:
                del self._ring[pos]
                self._sorted_keys.remove(pos)

    def get_shard(self, key):
        if not self._ring:
            raise ValueError("Empty ring")
        pos = self._hash(key)
        idx = bisect.bisect(self._sorted_keys, pos)
        if idx == len(self._sorted_keys):
            idx = 0
        return self._ring[self._sorted_keys[idx]]

    @property
    def shard_count(self):
        return len(set(self._ring.values()))
