"""
Beacon v0.10 — Toy Inverted Index

A minimal inverted index in pure Python, built to teach the data
structure that underlies every production search engine.

For 200,000 Beacon pages, this index would occupy approximately
200-400 MB in memory — manageable but wasteful. A production inverted
index (Lucene, Tantivy) uses compressed integer lists, skip lists,
and on-disk segments to handle billions of terms efficiently.

Building this 50-line index reveals three things:
1. Indexing is write-heavy — tokenization happens at write time.
2. Search is read-light — O(q) hash lookups, no document body scans.
3. Tokenization quality determines search quality.

Chapter 10, Principle 2: "Build the toy version first."
"""

import re
from collections import defaultdict
from typing import Dict, List, NamedTuple, Optional, Set


class Posting(NamedTuple):
    """A single occurrence of a term in a document."""
    doc_id: int
    position: int  # Word position within the document body.


class InvertedIndex:
    """
    A minimal inverted index in pure Python.

    Maps terms to sorted lists of Posting objects and documents
    to their data for retrieval. Supports AND-semantics search,
    term frequency, and document frequency queries.
    """

    def __init__(self):
        # term -> list of Posting objects.
        self._index: Dict[str, List[Posting]] = defaultdict(list)
        # doc_id -> document data for retrieval.
        self._documents: Dict[int, dict] = {}

    def add_document(self, doc_id: int, title: str, body: str):
        """
        Index a document by tokenizing its title and body.

        Tokenizer: lowercase, split on alphanumeric sequences
        (regex r'\w+'). This is a toy tokenizer. A real tokenizer
        handles Unicode normalization, stemming (running → run),
        stop word removal, and compound word splitting.

        Args:
            doc_id: Unique document identifier.
            title: Document title (boosted by being indexed first).
            body: Document body text.
        """
        self._documents[doc_id] = {"id": doc_id, "title": title, "body": body}

        # Tokenize: lowercase, split on non-alphanumeric characters.
        text = f"{title} {body}".lower()
        tokens = re.findall(r"\w+", text)

        for position, token in enumerate(tokens):
            self._index[token].append(Posting(doc_id, position))

    def search(self, query: str) -> List[dict]:
        """
        Return documents matching ALL query terms (AND semantics).

        Each term is looked up in the index. Matching document IDs
        are intersected. If any term matches nothing, returns [].

        Args:
            query: Space-separated search terms.

        Returns:
            List of document dicts matching all terms.
        """
        query_terms = query.lower().split()

        if not query_terms:
            return []

        # Find document IDs that contain ALL query terms.
        matching_ids: Optional[Set[int]] = None
        for term in query_terms:
            postings = self._index.get(term, [])
            term_doc_ids = {p.doc_id for p in postings}
            if matching_ids is None:
                matching_ids = term_doc_ids
            else:
                matching_ids &= term_doc_ids

            if not matching_ids:
                return []  # One term matched nothing — short-circuit.

        return [self._documents[doc_id] for doc_id in matching_ids]

    def term_frequency(self, term: str, doc_id: int) -> float:
        """
        How many times does ``term`` appear in ``doc_id``?

        Raw term frequency. A real index would use BM25 or TF-IDF
        weighting (see Section 10.4 of the manuscript).

        Args:
            term: The search term.
            doc_id: The document to check.

        Returns:
            Raw count of term occurrences in the document.
        """
        return sum(1 for p in self._index.get(term, []) if p.doc_id == doc_id)

    def document_frequency(self, term: str) -> int:
        """
        In how many documents does ``term`` appear?

        This is the denominator of IDF (inverse document frequency).

        Args:
            term: The search term.

        Returns:
            Number of documents containing the term.
        """
        return len({p.doc_id for p in self._index.get(term, [])})

    @property
    def document_count(self) -> int:
        """Total number of indexed documents."""
        return len(self._documents)

    @property
    def term_count(self) -> int:
        """Total number of unique terms in the index."""
        return len(self._index)
