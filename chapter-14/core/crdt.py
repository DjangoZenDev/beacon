"""Beacon v0.14 — CRDT (carried forward)."""
import uuid, time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Char:
    char_id: str; value: str; parent_id: str; client_id: str; lamport_ts: int
    START = "__START__"; END = "__END__"

@dataclass
class TextCRDT:
    site_id: str; chars: dict = field(default_factory=dict); clock: int = 0
    def __post_init__(self):
        self.chars = {}
        self._insert_sentinel(Char.START, Char.START)
        self._insert_sentinel(Char.END, Char.END)
    def _insert_sentinel(self, char_id, value):
        self.chars[char_id] = Char(char_id=char_id, value=value, parent_id=None, client_id=self.site_id, lamport_ts=0)
    def _tick(self): self.clock += 1; return self.clock
    def insert(self, char, after_id):
        ts = self._tick(); char_id = f"{ts}:{self.site_id}:{uuid.uuid4().hex[:8]}"
        new_char = Char(char_id=char_id, value=char, parent_id=after_id, client_id=self.site_id, lamport_ts=ts)
        self.chars[char_id] = new_char; return new_char
    def delete(self, char_id):
        if char_id in self.chars: self.chars[char_id].value = ""
    def get_text(self):
        children = {}; 
        for c in self.chars.values():
            pid = c.parent_id or Char.START
            children.setdefault(pid, []).append(c)
        for pid in children: children[pid].sort(key=lambda c: (c.lamport_ts, c.char_id))
        result = []
        def walk(nid):
            for child in children.get(nid, []):
                if child.value and child.value not in (Char.START, Char.END): result.append(child.value)
                walk(child.char_id)
        walk(Char.START); return "".join(result)
    def merge(self, remote_char):
        if remote_char.char_id not in self.chars:
            self.chars[remote_char.char_id] = remote_char
            self.clock = max(self.clock, remote_char.lamport_ts)
