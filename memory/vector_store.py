"""
memory/vector_store.py

Lightweight semantic search for trades and news.
Uses TF-IDF + cosine similarity — no external ML dependencies.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional


STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "and", "but", "or", "yet", "so", "if",
    "because", "although", "though", "while", "where", "when", "that",
    "which", "who", "whom", "whose", "what", "this", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their", "mine",
    "yours", "hers", "ours", "theirs", "am", "it", "s", "t", "just",
    "now", "then", "here", "there", "up", "down", "out", "off", "over",
    "again", "further", "once", "more", "most", "other", "some", "all",
    "any", "both", "each", "few", "many", "much", "several", "no", "not",
    "only", "own", "same", "such", "than", "too", "very", "also",
}


def _tokenize(text: str) -> List[str]:
    """Lowercase, extract words, remove stopwords."""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def _tf(tokens: List[str]) -> Dict[str, float]:
    """Term frequency of tokens."""
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()} if total else {}


def _idf(documents: List[List[str]]) -> Dict[str, float]:
    """Inverse document frequency."""
    n = len(documents)
    if n == 0:
        return {}
    doc_freq: Dict[str, int] = {}
    for doc in documents:
        seen = set(doc)
        for t in seen:
            doc_freq[t] = doc_freq.get(t, 0) + 1
    return {t: math.log(n / df) + 1 for t, df in doc_freq.items()}


def _dot_product(a: Dict[str, float], b: Dict[str, float]) -> float:
    return sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))


def _magnitude(v: Dict[str, float]) -> float:
    return math.sqrt(sum(x * x for x in v.values()))


def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    denom = _magnitude(a) * _magnitude(b)
    if denom == 0:
        return 0.0
    return _dot_product(a, b) / denom


class VectorStore:
    """
    Lightweight semantic document store.

    Stores documents with optional metadata and supports TF-IDF
    cosine-similarity search.
    """

    def __init__(self) -> None:
        self.documents: List[Dict[str, any]] = []
        self._tokens: List[List[str]] = []
        self._tfidf_vectors: List[Dict[str, float]] = []
        self._idf_cache: Optional[Dict[str, float]] = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, text: str, **metadata) -> None:
        """Add a document with optional metadata fields."""
        tokens = _tokenize(text)
        self.documents.append({"text": text, **metadata})
        self._tokens.append(tokens)
        self._idf_cache = None  # invalidate

    def clear(self) -> None:
        self.documents.clear()
        self._tokens.clear()
        self._tfidf_vectors.clear()
        self._idf_cache = None

    def count(self) -> int:
        return len(self.documents)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _rebuild_tfidf(self) -> None:
        """Rebuild TF-IDF vectors for all documents."""
        if not self._tokens:
            self._tfidf_vectors = []
            return

        idf = _idf(self._tokens)
        self._idf_cache = idf

        vectors = []
        for tokens in self._tokens:
            tf = _tf(tokens)
            vec = {t: tf_val * idf.get(t, 0) for t, tf_val in tf.items()}
            vectors.append(vec)
        self._tfidf_vectors = vectors

    def search(self, query: str, top_k: int = 5, min_score: float = 0.05) -> List[Dict[str, any]]:
        """
        TF-IDF cosine-similarity search.

        Returns documents ranked by relevance to the query.
        """
        if not self.documents:
            return []

        if self._idf_cache is None or len(self._tfidf_vectors) != len(self.documents):
            self._rebuild_tfidf()

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_tf = _tf(query_tokens)
        # Use same IDF as documents
        idf = self._idf_cache or {}
        query_vec = {t: tf_val * idf.get(t, 0) for t, tf_val in query_tf.items()}

        scored = []
        for idx, doc_vec in enumerate(self._tfidf_vectors):
            sim = _cosine_similarity(query_vec, doc_vec)
            if sim >= min_score:
                doc = self.documents[idx].copy()
                doc["score"] = round(sim, 4)
                scored.append((sim, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def keyword_search(self, query: str) -> List[Dict[str, any]]:
        """Original simple keyword search (case-insensitive substring match)."""
        q = query.lower()
        return [doc for doc in self.documents if q in doc.get("text", "").lower()]
