"""NLP baselines and semantic-model evidence (Phases 6-7)."""

from verireview.semantic.scorers import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingScorer,
    LexicalScorer,
    Scorer,
    TfidfScorer,
)
from verireview.semantic.text import change_text, comment_text, words
from verireview.semantic.verifier import SimilarityVerifier

__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "EmbeddingScorer",
    "LexicalScorer",
    "Scorer",
    "SimilarityVerifier",
    "TfidfScorer",
    "change_text",
    "comment_text",
    "words",
]
