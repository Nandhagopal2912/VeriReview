"""NLP baselines and semantic-model evidence (Phases 6-7).

Nothing here imports torch / transformers / sentence-transformers at import time.
"""

from verireview.semantic.code_model import (
    DEFAULT_CODE_MODEL,
    DEFAULT_CODE_MODEL_REVISION,
    CodeModelScorer,
    UniXcoderEncoder,
    default_code_encoder,
)
from verireview.semantic.code_view import CodeChunk, change_chunks, code_change_text
from verireview.semantic.scorers import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingScorer,
    Encoder,
    LexicalScorer,
    Scorer,
    TfidfScorer,
)
from verireview.semantic.text import change_text, comment_text, words
from verireview.semantic.verifier import VIEWS, SimilarityVerifier, View

__all__ = [
    "DEFAULT_CODE_MODEL",
    "DEFAULT_CODE_MODEL_REVISION",
    "DEFAULT_EMBEDDING_MODEL",
    "VIEWS",
    "CodeChunk",
    "CodeModelScorer",
    "EmbeddingScorer",
    "Encoder",
    "LexicalScorer",
    "Scorer",
    "SimilarityVerifier",
    "TfidfScorer",
    "UniXcoderEncoder",
    "View",
    "change_chunks",
    "change_text",
    "code_change_text",
    "comment_text",
    "default_code_encoder",
    "words",
]
