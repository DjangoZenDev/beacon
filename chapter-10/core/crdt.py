"""
Beacon v0.10 — Minimal Text CRDT (carried from Ch9).

A conflict-free replicated text document. Every character receives a
globally unique identifier (Lamport timestamp + client id + random suffix)
and a parent reference. The document is a tree, not a string. The display
order is a deterministic depth-first traversal of that tree.
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Char:
    char_id: str
    value: str
    parent_id: str
    client_id: str
    lamport_ts: int
    START = "__START__"
    END = "__END__"


@dataclass
class TextCRDT:
    site_id: str
    chars: dict = field(default_factory=dict)
    clock: int = 0

    def __post_init__(self):
        self.chars = {}
        self._insert_sentinel(Char.START, Char.START)
        self._insert_sentinel(Char.END, Char.END)

    def _insert_sentinel(self, char_id: str, value: str):
        self.chars[char_id] = Char(char_id=char_id, value=value, parent_id=None, client_id=self.site_id, lamport_ts=0)

    def _tick(self) -> int:
        self.clock += 1
        return self.clock

    def insert(self, char: str, after_id: str) -> Char:
        ts = self._tick()
        char_id = f"{ts}:{self.site_id}:{uuid.uuid4().hex[:8]}"
        new_char = Char(char_id=char_id, value=char, parent_id=after_id, client_id=self.site_id, lamport_ts=ts)
        self.chars[char_id] = new_char
        return new_char

    def delete(self, char_id: str):
        if char_id in self.chars:
            self.chars[char_id].value = ""

    def get_text(self) -> str:
        children: Dict[str, List[Char]] = {}
        for c in self.chars.values():
            pid = c.parent_id or Char.START
            if pid not in children:
                children[pid] = []
            children[pid].append(c)
        for pid in children:
            children[pid].sort(key=lambda c: (c.lamport_ts, c.char_id))
        result: List[str] = []
        def walk(node_id: str):
            for child in children.get(node_id, []):
                if child.value and child.value not in (Char.START, Char.END):
                    result.append(child.value)
                walk(child.char_id)
        walk(Char.START)
        return "".join(result)

    def merge(self, remote_char: Char):
        if remote_char.char_id not in self.chars:
            self.chars[remote_char.char_id] = remote_char
            self.clock = max(self.clock, remote_char.lamport_ts)


def demo() -> bool:
    replica_a = TextCRDT(site_id="alice")
    replica_b = TextCRDT(site_id="bob")
    c_a1 = replica_a.insert("a", Char.START)
    c_a2 = replica_a.insert("b", c_a1.char_id)
    c_b1 = replica_b.insert("x", Char.START)
    c_b2 = replica_b.insert("y", c_b1.char_id)
    for char in replica_a.chars.values():
        replica_b.merge(char)
    for char in replica_b.chars.values():
        replica_a.merge(char)
    text_a = replica_a.get_text()
    text_b = replica_b.get_text()
    print(f"Replica A: '{text_a}'")
    print(f"Replica B: '{text_b}'")
    assert replica_a.get_text() == replica_b.get_text(), f"CRDT divergence! A='{text_a}' B='{text_b}'"
    print("✓ CRDTs converged successfully.")
    return True


if __name__ == "__main__":
    demo()
