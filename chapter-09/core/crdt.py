
"""
Beacon v0.9 — Minimal Text CRDT

A conflict-free replicated text document. Every character receives a
globally unique identifier (Lamport timestamp + client id + random suffix)
and a parent reference. The document is a tree, not a string. The display
order is a deterministic depth-first traversal of that tree.

Because every character has a unique ID and a stable parent reference,
the tree converges to the same order on every replica regardless of
insertion order. This is strong eventual consistency: no consensus,
no leader election, no conflict resolution code — just math.

Chapter 9, Principle 1: "CRDTs win by avoiding conflict, not by resolving it."
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Char:
    """
    A single character in a CRDT document.

    Each character has a globally unique identifier and a reference
    to the character it was inserted after. This creates a linked-list
    structure that converges regardless of insertion order.

    Attributes:
        char_id: Globally unique: "{lamport_ts}:{client_id}:{random}"
        value: The actual character (empty string = tombstone).
        parent_id: ID of the character this was inserted after.
        client_id: Which client created this character.
        lamport_ts: Lamport timestamp for causal ordering.
    """

    char_id: str
    value: str
    parent_id: str
    client_id: str
    lamport_ts: int

    # Special sentinel values for the start and end of the document.
    START = "__START__"
    END = "__END__"


@dataclass
class TextCRDT:
    """
    A conflict-free replicated text document.

    Characters are stored in a flat dictionary keyed by char_id.
    The document text is recovered by walking the implicit tree
    from START to END, sorting children by Lamport timestamp.
    """

    site_id: str
    chars: dict = field(default_factory=dict)
    clock: int = 0

    def __post_init__(self):
        """Initialize with START and END sentinels."""
        self.chars = {}
        self._insert_sentinel(Char.START, Char.START)
        self._insert_sentinel(Char.END, Char.END)

    def _insert_sentinel(self, char_id: str, value: str):
        """Insert a sentinel character (START or END)."""
        self.chars[char_id] = Char(
            char_id=char_id,
            value=value,
            parent_id=None,
            client_id=self.site_id,
            lamport_ts=0,
        )

    def _tick(self) -> int:
        """Increment the Lamport clock and return the new value."""
        self.clock += 1
        return self.clock

    def insert(self, char: str, after_id: str) -> Char:
        """
        Insert a character after the character with the given ID.

        Args:
            char: The single character to insert.
            after_id: The char_id of the character to insert after.
                      Use Char.START to insert at the beginning.

        Returns:
            The newly created Char object.
        """
        ts = self._tick()
        char_id = f"{ts}:{self.site_id}:{uuid.uuid4().hex[:8]}"

        new_char = Char(
            char_id=char_id,
            value=char,
            parent_id=after_id,
            client_id=self.site_id,
            lamport_ts=ts,
        )
        self.chars[char_id] = new_char
        return new_char

    def delete(self, char_id: str):
        """
        Tombstone a character — we never truly remove it.

        CRDTs require that we preserve the tree structure even for
        deleted characters. Setting value to "" creates a tombstone.
        """
        if char_id in self.chars:
            self.chars[char_id].value = ""

    def get_text(self) -> str:
        """
        Walk the implicit tree from START, following children in
        insertion order, to produce the converged document text.

        Returns:
            The full document text as a single string.
        """
        # Build the tree: parent_id → list of children.
        children: Dict[str, List[Char]] = {}
        for c in self.chars.values():
            pid = c.parent_id or Char.START
            if pid not in children:
                children[pid] = []
            children[pid].append(c)

        # Sort children by Lamport timestamp (tiebreak by char_id).
        for pid in children:
            children[pid].sort(key=lambda c: (c.lamport_ts, c.char_id))

        # Depth-first walk from START.
        result: List[str] = []

        def walk(node_id: str):
            for child in children.get(node_id, []):
                if child.value and child.value not in (Char.START, Char.END):
                    result.append(child.value)
                walk(child.char_id)

        walk(Char.START)
        return "".join(result)

    def merge(self, remote_char: Char):
        """
        Apply a remote character insertion locally.

        If the character is already known (same char_id), it is
        idempotently ignored. Otherwise it is added and our clock
        is advanced to maintain causal ordering.

        Args:
            remote_char: A Char object received from a remote replica.
        """
        if remote_char.char_id not in self.chars:
            self.chars[remote_char.char_id] = remote_char
            # Advance our Lamport clock to maintain causal ordering.
            self.clock = max(self.clock, remote_char.lamport_ts)


# ── Demo: prove CRDT convergence ─────────────────────────────────

def demo() -> bool:
    """
    Demonstrate that two independent CRDT replicas converge to
    identical document text after merging all operations.

    Returns:
        True if convergence is verified, raises AssertionError otherwise.
    """
    replica_a = TextCRDT(site_id="alice")
    replica_b = TextCRDT(site_id="bob")

    # Alice types "ab"
    c_a1 = replica_a.insert("a", Char.START)
    c_a2 = replica_a.insert("b", c_a1.char_id)

    # Bob types "xy" independently
    c_b1 = replica_b.insert("x", Char.START)
    c_b2 = replica_b.insert("y", c_b1.char_id)

    # Sync: merge all characters into both replicas.
    for char in replica_a.chars.values():
        replica_b.merge(char)
    for char in replica_b.chars.values():
        replica_a.merge(char)

    text_a = replica_a.get_text()
    text_b = replica_b.get_text()

    print(f"Replica A: '{text_a}'")
    print(f"Replica B: '{text_b}'")
    print(f"  Both contain 'ab': {'ab' in text_a and 'ab' in text_b}")
    print(f"  Both contain 'xy': {'xy' in text_a and 'xy' in text_b}")

    assert replica_a.get_text() == replica_b.get_text(), (
        f"CRDT divergence! A='{text_a}' B='{text_b}'"
    )
    print("✓ CRDTs converged successfully.")
    return True


if __name__ == "__main__":
    demo()
