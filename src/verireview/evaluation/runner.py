"""Run a pipeline over fixtures and produce a reproducible evaluation report."""

import hashlib
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel

from verireview.contracts import Confidence, Verdict
from verireview.dataset import Fixture
from verireview.evaluation.metrics import Metrics, compute_metrics
from verireview.verification import Pipeline


class CaseOutcome(BaseModel):
    case_id: str
    category: str
    hard_case: str | None
    expected: Verdict
    predicted: Verdict
    confidence: Confidence

    @property
    def correct(self) -> bool:
        return self.expected == self.predicted


class EvaluationReport(BaseModel):
    pipeline_version: str
    dataset_hash: str
    metrics: Metrics
    accuracy_by_category: dict[str, float]
    accuracy_by_hard_case: dict[str, float]
    cases: list[CaseOutcome]


def evaluate(
    pipeline: Pipeline, fixtures: Sequence[Fixture], dataset_root: Path
) -> EvaluationReport:
    outcomes = []
    for fixture in fixtures:
        result = pipeline.run(fixture.case)
        outcomes.append(
            CaseOutcome(
                case_id=fixture.meta.case_id,
                category=fixture.meta.category.value,
                hard_case=fixture.meta.hard_case.value if fixture.meta.hard_case else None,
                expected=fixture.meta.expected_verdict,
                predicted=result.verdict,
                confidence=result.confidence,
            )
        )
    return EvaluationReport(
        pipeline_version=pipeline.version,
        dataset_hash=dataset_hash(dataset_root),
        metrics=compute_metrics([(o.expected, o.predicted) for o in outcomes]),
        accuracy_by_category=_accuracy_by(outcomes, lambda o: o.category),
        accuracy_by_hard_case=_accuracy_by(outcomes, lambda o: o.hard_case or "none"),
        cases=outcomes,
    )


def dataset_hash(root: Path) -> str:
    """SHA-256 over every fixture file (path + content, LF-normalised): pins the exact dataset."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def _accuracy_by(
    outcomes: list[CaseOutcome], key: Callable[[CaseOutcome], str]
) -> dict[str, float]:
    groups: dict[str, list[bool]] = defaultdict(list)
    for o in outcomes:
        groups[key(o)].append(o.correct)
    return {k: sum(v) / len(v) for k, v in sorted(groups.items())}
