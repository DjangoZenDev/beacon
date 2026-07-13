
"""
Beacon v0.13 — Toy Inverted Index

A minimal inverted index in pure Python, built to teach the data
structure that underlies every production search engine.

Chapter 10, Principle 2: "Build the toy version first."
Carried forward unchanged through Chapter 13.
"""

import re
from collections import defaultdict
from typing import Dict, List, NamedTuple, Optional, Set


class Posting(NamedTuple):
    doc_id: int
    position: int


class InvertedIndex:
    def __init__(self):
        self._index: Dict[str, List[Posting]] = defaultdict(list)
        self._documents: Dict[int, dict] = {}

    def add_document(self, doc_id: int, title: str, body: str):
        self._documents[doc_id] = {"id": doc_id, "title": title, "body": body}
        text = f"{title} {body}".lower()
        tokens = re.findall(r"\w+", text)
        for position, token in enumerate(tokens):
            self._index[token].append(Posting(doc_id, position))

    def search(self, query: str) -> List[dict]:
        query_terms = query.lower().split()
        if not query_terms: return []
        matching_ids: Optional[Set[int]] = None
        for term in query_terms:
            postings = self._index.get(term, [])
            term_doc_ids = {p.doc_id for p in postings}
            if matching_ids is None: matching_ids = term_doc_ids
            else: matching_ids &= term_doc_ids
            if not matching_ids: return []
        return [self._documents[doc_id] for doc_id in matching_ids]

    def term_frequency(self, term: str, doc_id: int) -> float:
        return sum(1 for p in self._index.get(term, []) if p.doc_id == doc_id)

    def document_frequency(self, term: str) -> int:
        return len({p.doc_id for p in self._index.get(term, [])})

    @property
    def document_count(self) -> int: return len(self._documents)

    @property
    def term_count(self) -> int: return len(self._index)
