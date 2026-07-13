"""Beacon v0.14 — Inverted Index (toy)."""
import re; from collections import defaultdict; from typing import Dict, List, NamedTuple, Optional, Set
class Posting(NamedTuple): doc_id: int; position: int
class InvertedIndex:
    def __init__(self): self._index: Dict[str, List[Posting]] = defaultdict(list); self._documents: Dict[int, dict] = {}
    def add_document(self, doc_id, title, body):
        self._documents[doc_id] = {"id": doc_id, "title": title, "body": body}
        text = f"{title} {body}".lower(); tokens = re.findall(r"\w+", text)
        for position, token in enumerate(tokens): self._index[token].append(Posting(doc_id, position))
    def search(self, query):
        terms = query.lower().split(); 
        if not terms: return []
        matching_ids: Optional[Set[int]] = None
        for term in terms:
            tids = {p.doc_id for p in self._index.get(term, [])}
            matching_ids = tids if matching_ids is None else matching_ids & tids
            if not matching_ids: return []
        return [self._documents[did] for did in matching_ids]
    def term_frequency(self, term, doc_id): return sum(1 for p in self._index.get(term,[]) if p.doc_id==doc_id)
    def document_frequency(self, term): return len({p.doc_id for p in self._index.get(term,[])})
    @property
    def document_count(self): return len(self._documents)
    @property
    def term_count(self): return len(self._index)
