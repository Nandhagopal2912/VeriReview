"""Semantic evidence (Phase 7): how relevant is the added code to each requirement?

For each requirement, the code model (UniXcoder) compares the requirement's description with
every chunk of added code (comments and docstrings removed, `semantic.code_view`). It reports
the best-matching chunk, with its location, as one ``semantic_relevance`` item.

The item is **neutral** (``passed=None``): no aggregator reads it, so verdicts stay those of the
rules. It shows a human reviewer which added code the model links to each requirement. Whether
it may ever influence a verdict is decided in Phase 8b, on dev data only (roadmap).
"""

from dataclasses import dataclass
from typing import Any

from verireview.contracts import (
    CodeLocation,
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
)
from verireview.semantic import CodeChunk, Encoder, change_chunks, default_code_encoder

KIND = "semantic_relevance"


@dataclass(frozen=True)
class Relevance:
    requirement_id: str
    score: float  # cosine similarity of the best-matching chunk
    chunk: CodeChunk
    candidates: int  # number of added code chunks compared


def requirement_relevance(
    case: ReviewCase, requirement: ReviewRequirement, encoder: Encoder
) -> list[Relevance]:
    """Best-matching added code chunk per requirement ([] when no code was added)."""
    chunks = change_chunks(case)
    if not chunks:
        return []
    texts = [r.description for r in requirement.requirements]
    vectors = encoder(texts + [c.text for c in chunks])
    wanted, found = vectors[: len(texts)], vectors[len(texts) :]
    out = []
    for req, vector in zip(requirement.requirements, wanted, strict=True):
        scores = [_cosine(vector, chunk) for chunk in found]
        best = max(range(len(chunks)), key=lambda i: scores[i])  # ties: the first chunk
        out.append(Relevance(req.id, scores[best], chunks[best], len(chunks)))
    return out


@dataclass(frozen=True)
class SemanticRelevanceStage:
    """Evidence stage; ``encoder`` defaults to the shared UniXcoder encoder (loaded lazily)."""

    encoder: Encoder | None = None
    model_name: str = "unixcoder"

    def __call__(self, case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
        encoder = self.encoder or default_code_encoder()
        return [
            Evidence(
                id="?",
                requirement_id=r.requirement_id,
                source=EvidenceSource.SEMANTIC,
                kind=KIND,
                passed=None,
                detail=f"Code-model relevance of {r.requirement_id} to the added code: "
                f"{r.score:.2f}, best of {r.candidates} added chunk(s) "
                f"({self.model_name}; informational, does not affect the verdict).",
                location=CodeLocation(
                    file=r.chunk.file,
                    line_start=r.chunk.line_start,
                    line_end=r.chunk.line_end,
                    version="after",
                ),
            )
            for r in requirement_relevance(case, requirement, encoder)
        ]


def _cosine(a: Any, b: Any) -> float:
    norm = float((a @ a) ** 0.5 * (b @ b) ** 0.5)
    return float(a @ b) / norm if norm else 0.0
