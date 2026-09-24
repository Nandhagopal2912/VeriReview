"""The pre-registered ablation systems of Phase 10 (docs/phase10_protocol.md).

Similarity baselines get one threshold, Youden's J on the dev split; nothing is tuned on test.
Model-backed systems (B, B', E) need the optional `nlp` group and are imported lazily.
"""

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from verireview.benchmark import BenchmarkCase
from verireview.evaluation.benchmark import (
    PairedDifference,
    System,
    SystemResult,
    youden_on_dev,
)
from verireview.evaluation.runner import Verifier


class BenchmarkReport(BaseModel):
    split: str
    commit: str
    manifest_version: str | None
    protocol_sha256: str
    dataset_hashes: dict[str, str]
    resamples: int
    bootstrap_seed: int
    n_cases: int
    systems: list[SystemResult]
    paired_vs_full: list[PairedDifference]
    skipped: list[str]


def _similarity(
    scorer_factory: Callable[[], Any], view: str
) -> Callable[[Sequence[BenchmarkCase]], tuple[Verifier, dict[str, Any]]]:
    def build(dev: Sequence[BenchmarkCase]) -> tuple[Verifier, dict[str, Any]]:
        from verireview.semantic import SimilarityVerifier, comment_text

        scorer = scorer_factory()
        probe = SimilarityVerifier(scorer, 0.0, view)  # type: ignore[arg-type]
        scorer.fit(
            [comment_text(c.fixture.case) for c in dev]
            + [probe.change(c.fixture.case) for c in dev]
        )
        threshold = youden_on_dev(lambda c: probe.score(c.fixture.case), dev)
        verifier = SimilarityVerifier(scorer, threshold, view)  # type: ignore[arg-type]
        return verifier, {"threshold": threshold, "view": view, **scorer.describe()}

    return build


def _pipeline(name: str) -> Callable[[Sequence[BenchmarkCase]], tuple[Verifier, dict[str, Any]]]:
    def build(dev: Sequence[BenchmarkCase]) -> tuple[Verifier, dict[str, Any]]:
        from verireview.verification import get_pipeline

        return get_pipeline(name), {"pipeline": name}

    return build


def _lexical() -> Any:
    from verireview.semantic import LexicalScorer

    return LexicalScorer()


def _embedding() -> Any:
    from verireview.semantic import EmbeddingScorer

    return EmbeddingScorer()


def _unixcoder() -> Any:
    from verireview.semantic import CodeModelScorer

    return CodeModelScorer()


SYSTEMS: tuple[System, ...] = (
    System("A", "A keyword / lexical", _similarity(_lexical, "added")),
    System(
        "B", "B embedding similarity (MiniLM)", _similarity(_embedding, "added"), needs_models=True
    ),
    System(
        "B'",
        "B code-aware embedding (UniXcoder, code view)",
        _similarity(_unixcoder, "code"),
        needs_models=True,
    ),
    System("L", "diff locality (phase2)", _pipeline("phase2-locality")),
    System("S", "AST structure, no rules (phase3)", _pipeline("phase3-structure")),
    System("R", "requirements + AST (phase4)", _pipeline("phase4-requirements")),
    System("C/D", "C/D rules + AST (phase5)", _pipeline("phase5-rules")),
    System(
        "E",
        "E rules + AST + semantic model (phase7)",
        _pipeline("phase7-semantic"),
        needs_models=True,
    ),
    System("F", "F full VeriReview (mvp)", _pipeline("mvp")),
    System(
        "F-gold", "F with gold requirements (diagnostic)", _pipeline("mvp"), gold_requirements=True
    ),
)
