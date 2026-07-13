
"""
Beacon v0.11 — Minimal Text CRDT (carried from Ch9-10).
"""
import uuid, time
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Char:
    char_id: str; value: str; parent_id: str; client_id: str; lamport_ts: int
    START = "__START__"; END = "__END__"

@dataclass
class TextCRDT:
    site_id: str; chars: dict = field(default_factory=dict); clock: int = 0
    def __post_init__(self):
        self.chars = {}; self._insert_sentinel(Char.START, Char.START); self._insert_sentinel(Char.END, Char.END)
    def _insert_sentinel(self, char_id, value): self.chars[char_id] = Char(char_id=char_id, value=value, parent_id=None, client_id=self.site_id, lamport_ts=0)
    def _tick(self) -> int: self.clock += 1; return self.clock
    def insert(self, char: str, after_id: str) -> Char:
        ts = self._tick(); char_id = f"{ts}:{self.site_id}:{uuid.uuid4().hex[:8]}"
        nc = Char(char_id=char_id, value=char, parent_id=after_id, client_id=self.site_id, lamport_ts=ts); self.chars[char_id] = nc; return nc
    def delete(self, char_id: str):
        if char_id in self.chars: self.chars[char_id].value = ""
    def get_text(self) -> str:
        children: Dict[str, List[Char]] = {}
        for c in self.chars.values():
            pid = c.parent_id or Char.START
            if pid not in children: children[pid] = []
            children[pid].append(c)
        for pid in children: children[pid].sort(key=lambda c: (c.lamport_ts, c.char_id))
        result: List[str] = []
        def walk(nid):
            for child in children.get(nid, []):
                if child.value and child.value not in (Char.START, Char.END): result.append(child.value)
                walk(child.char_id)
        walk(Char.START); return "".join(result)
    def merge(self, remote_char: Char):
        if remote_char.char_id not in self.chars: self.chars[remote_char.char_id] = remote_char; self.clock = max(self.clock, remote_char.lamport_ts)

def demo() -> bool:
    a = TextCRDT(site_id="alice"); b = TextCRDT(site_id="bob")
    ca1 = a.insert("a", Char.START); a.insert("b", ca1.char_id)
    cb1 = b.insert("x", Char.START); b.insert("y", cb1.char_id)
    for c in a.chars.values(): b.merge(c)
    for c in b.chars.values(): a.merge(c)
    assert a.get_text() == b.get_text(), f"CRDT divergence!"; print("✓ CRDTs converged."); return True
if __name__ == "__main__": demo()
