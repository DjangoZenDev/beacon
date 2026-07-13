
"""
Beacon v0.6 — Consistent Hash Ring

A consistent hashing ring implementation with MD5-based key hashing
and 150 virtual replicas per shard. Used by OrganizationShardRouter
to route database operations to the correct shard.

The ring maps organization_id values to shard database aliases
(shard-0, shard-1, etc.). Virtual replicas ensure even distribution
even with a small number of physical shards.

Why MD5? For shard routing, cryptographic strength is irrelevant.
MD5 is fast (sub-microsecond per call), deterministic, and produces
a uniform 128-bit output. The distribution quality is what matters,
and MD5's uniformity is excellent. The known collision vulnerabilities
in MD5 do not affect hash ring distribution.

Chapter 6, Principle 8: "Consistent hashing is worth building yourself."
"""

import hashlib
import bisect


class ConsistentHashRing:
    """
    A consistent hash ring for mapping keys to shards.

    Each shard is represented by `replicas` virtual nodes on the ring.
    When a key is hashed, we walk clockwise around the ring and return
    the first shard we encounter.

    Virtual replicas (150 by default) ensure that adding or removing a
    shard redistributes only ~1/N of keys rather than all keys. With
    4 shards and 150 replicas, adding a 5th shard redistributes ~25%
    of keys — close to the theoretical minimum of 20%.
    """

    def __init__(self, shards=None, replicas=150):
        """
        Initialize the ring.

        Args:
            shards: Optional list of shard names (e.g., ["shard-0", "shard-1"]).
            replicas: Number of virtual nodes per shard. Higher values
                      produce more even distribution at the cost of a
                      slightly larger in-memory structure.
        """
        self.replicas = replicas
        self._ring: dict[int, str] = {}  # hash_position -> shard_name
        self._sorted_keys: list[int] = []  # sorted hash positions for bisect

        if shards:
            for shard in shards:
                self.add_shard(shard)

    def _hash(self, key) -> int:
        """
        Hash a key to an integer position on the ring.

        Uses MD5 for speed and uniform distribution. The key is
        stringified before hashing so both ints and strings work.
        """
        key_bytes = str(key).encode("utf-8")
        digest = hashlib.md5(key_bytes).hexdigest()
        # Use first 8 bytes of the hex digest as a 32-bit integer.
        return int(digest[:8], 16)

    def add_shard(self, shard_name: str):
        """
        Add a shard to the ring with `replicas` virtual nodes.

        Virtual nodes are named "{shard_name}:0", "{shard_name}:1", etc.
        This ensures the shard appears at multiple positions on the ring.
        """
        for i in range(self.replicas):
            node_key = f"{shard_name}:{i}"
            position = self._hash(node_key)
            self._ring[position] = shard_name
            bisect.insort(self._sorted_keys, position)

    def remove_shard(self, shard_name: str):
        """
        Remove a shard and all its virtual nodes from the ring.

        Keys that mapped to this shard will be redistributed to the
        next shard clockwise on the ring.
        """
        for i in range(self.replicas):
            node_key = f"{shard_name}:{i}"
            position = self._hash(node_key)
            if position in self._ring:
                del self._ring[position]
                self._sorted_keys.remove(position)

    def get_shard(self, key: int) -> str:
        """
        Return the shard responsible for the given key.

        Uses bisect to find the first ring position >= hash(key).
        If the hash wraps past the end of the ring, returns the
        first shard (wrap-around).

        Args:
            key: The shard key, typically an organization_id.

        Returns:
            The shard name (e.g., "shard-2").

        Raises:
            ValueError: If the ring is empty (no shards added).
        """
        if not self._ring:
            raise ValueError("Hash ring is empty — no shards configured.")

        position = self._hash(key)
        idx = bisect.bisect(self._sorted_keys, position)

        # Wrap around the ring if we went past the last position.
        if idx == len(self._sorted_keys):
            idx = 0

        return self._ring[self._sorted_keys[idx]]

    @property
    def shard_count(self):
        """Number of unique shards currently in the ring."""
        return len(set(self._ring.values()))
