"""Similarity scorers for the Phase 6 baselines: comment text vs. added code, in [0, 1].

A. LexicalScorer    share of the comment's content words that appear in the change
B. TfidfScorer      TF-IDF cosine similarity; vectorizer fitted on the dev corpus only
C. EmbeddingScorer  sentence-embedding cosine similarity (sentence-transformers, CPU)

Each scorer is deterministic after ``fit``. ML libraries are imported lazily, so the default
install (no `nlp` group) can still import this module.
"""

from collections.abc import Callable, Sequence
from typing import Any, Protocol

from verireview.semantic.text import words

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Scorer(Protocol):
    name: str

    def fit(self, corpus: Sequence[str]) -> None: ...

    def score(self, comment: str, change: str) -> float: ...

    def describe(self) -> dict[str, Any]: ...


class LexicalScorer:
    """Keyword baseline (plan §13, baseline 1): overlap of content words."""

    name = "lexical"

    def fit(self, corpus: Sequence[str]) -> None:
        """Nothing to learn."""

    def score(self, comment: str, change: str) -> float:
        wanted = set(words(comment))
        if not wanted or not change.strip():
            return 0.0
        return len(wanted & set(words(change))) / len(wanted)

    def describe(self) -> dict[str, Any]:
        return {"scorer": self.name, "measure": "|comment words ∩ change words| / |comment words|"}


class TfidfScorer:
    """TF-IDF baseline (plan §13, baseline 2): cosine similarity of TF-IDF vectors."""

    name = "tfidf"

    def __init__(self) -> None:
        self._vectorizer: Any = None

    def fit(self, corpus: Sequence[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            analyzer=words, sublinear_tf=True, norm="l2", lowercase=False
        )
        self._vectorizer.fit(list(corpus))

    def score(self, comment: str, change: str) -> float:
        if self._vectorizer is None:
            raise RuntimeError("TfidfScorer.fit() must be called first (on the dev corpus)")
        if not change.strip():
            return 0.0
        vectors = self._vectorizer.transform([comment, change])
        return float((vectors[0] @ vectors[1].T).toarray()[0, 0])  # rows are L2-normalised

    def describe(self) -> dict[str, Any]:
        size = len(self._vectorizer.vocabulary_) if self._vectorizer is not None else 0
        return {"scorer": self.name, "vocabulary_size": size, "fitted_on": "dev corpus"}


Encoder = Callable[[list[str]], Any]  # texts → array of shape (n, dim)


class EmbeddingScorer:
    """Embedding baseline (plan §13, baseline 3): cosine similarity of sentence embeddings."""

    name = "embedding"

    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL, encoder: Encoder | None = None):
        self.model = model
        self._encoder = encoder

    def fit(self, corpus: Sequence[str]) -> None:
        """Pretrained; nothing is fitted (the threshold is tuned by the harness)."""

    def score(self, comment: str, change: str) -> float:
        if not change.strip():
            return 0.0
        a, b = self._encode([comment, change])
        denominator = float((a @ a) ** 0.5 * (b @ b) ** 0.5)
        return float(a @ b) / denominator if denominator else 0.0

    def describe(self) -> dict[str, Any]:
        return {"scorer": self.name, "model": self.model, "device": "cpu"}

    def _encode(self, texts: list[str]) -> Any:
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model, device="cpu")
            self._encoder = lambda batch: model.encode(batch, convert_to_numpy=True)
        return self._encoder(texts)
