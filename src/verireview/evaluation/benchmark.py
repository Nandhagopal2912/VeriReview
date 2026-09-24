"""Phase 10: the ablation study on a benchmark split (docs/phase10_protocol.md, pre-registered).

Every system is scored the same way: one verdict per case, then metrics on the pooled split and per
source (controlled / adversarial / real_world), with percentile bootstrap intervals and paired
bootstrap differences against the full system (F).
"""

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from verireview.benchmark import BenchmarkCase
from verireview.contracts import Confidence, Verdict
from verireview.evaluation.baselines import tune_threshold_youden
from verireview.evaluation.metrics import Metrics, compute_metrics
from verireview.evaluation.runner import Verifier

BOOTSTRAP_SEED = 20260924
FULL_SYSTEM = "F"


class CaseRecord(BaseModel):
    case_id: str
    source: str
    category: str
    hard_case: str | None
    expected: Verdict
    predicted: Verdict
    confidence: Confidence


class Interval(BaseModel):
    estimate: float | None
    low: float | None
    high: float | None


class SliceResult(BaseModel):
    n: int
    metrics: Metrics
    coverage: float | None
    selective_accuracy: float | None
    intervals: dict[str, Interval]
    accuracy_by_category: dict[str, float]
    accuracy_by_hard_case: dict[str, float]


class SystemResult(BaseModel):
    system: str
    plan_row: str
    version: str
    config: dict[str, Any]
    pooled: SliceResult
    by_source: dict[str, SliceResult]
    accuracy_by_confidence: dict[str, float]
    cases: list[CaseRecord]


class PairedDifference(BaseModel):
    other: str
    accuracy: Interval  # F minus other
    false_acceptance_rate: Interval


@dataclass(frozen=True)
class System:
    """One row of the ablation. ``build`` gets the dev cases (for threshold tuning only)."""

    name: str
    plan_row: str
    build: Callable[[Sequence[BenchmarkCase]], tuple[Verifier, dict[str, Any]]]
    gold_requirements: bool = False
    needs_models: bool = False
    notes: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- running


def run_system(
    system: System, cases: Sequence[BenchmarkCase], dev: Sequence[BenchmarkCase]
) -> tuple[list[CaseRecord], str, dict[str, Any]]:
    verifier, config = system.build(dev)
    records = []
    for bc in cases:
        fixture = bc.fixture
        override = fixture.gold_requirement if system.gold_requirements else None
        result = verifier.run(fixture.case, override)
        records.append(
            CaseRecord(
                case_id=fixture.meta.case_id,
                source=bc.source.value,
                category=fixture.meta.category.value,
                hard_case=fixture.meta.hard_case.value if fixture.meta.hard_case else None,
                expected=fixture.meta.expected_verdict,
                predicted=result.verdict,
                confidence=result.confidence,
            )
        )
    version = verifier.version + ("+gold-requirements" if system.gold_requirements else "")
    return records, version, config


def evaluate_system(
    system: System,
    cases: Sequence[BenchmarkCase],
    dev: Sequence[BenchmarkCase],
    resamples: int,
) -> SystemResult:
    records, version, config = run_system(system, cases, dev)
    sources = sorted({r.source for r in records})
    return SystemResult(
        system=system.name,
        plan_row=system.plan_row,
        version=version,
        config={**config, **system.notes},
        pooled=slice_result(records, resamples),
        by_source={
            s: slice_result([r for r in records if r.source == s], resamples) for s in sources
        },
        accuracy_by_confidence=_accuracy_by(records, lambda r: r.confidence.value),
        cases=records,
    )


# ---------------------------------------------------------------- metrics


def coverage(records: Sequence[CaseRecord]) -> float | None:
    """Share of cases with a decided verdict (not UNCERTAIN)."""
    if not records:
        return None
    return sum(r.predicted != Verdict.UNCERTAIN for r in records) / len(records)


def selective_accuracy(records: Sequence[CaseRecord]) -> float | None:
    decided = [r for r in records if r.predicted != Verdict.UNCERTAIN]
    if not decided:
        return None
    return sum(r.predicted == r.expected for r in decided) / len(decided)


STATISTICS: dict[str, Callable[[Sequence[CaseRecord]], float | None]] = {
    "accuracy": lambda rs: _metrics(rs).accuracy if rs else None,
    "macro_f1": lambda rs: _metrics(rs).macro_f1 if rs else None,
    "false_acceptance_rate": lambda rs: _metrics(rs).false_acceptance_rate,
    "false_blocking_rate": lambda rs: _metrics(rs).false_blocking_rate,
    "coverage": coverage,
}


def slice_result(records: Sequence[CaseRecord], resamples: int) -> SliceResult:
    return SliceResult(
        n=len(records),
        metrics=_metrics(records),
        coverage=coverage(records),
        selective_accuracy=selective_accuracy(records),
        intervals={
            name: bootstrap_interval(records, stat, resamples) for name, stat in STATISTICS.items()
        },
        accuracy_by_category=_accuracy_by(records, lambda r: r.category),
        accuracy_by_hard_case=_accuracy_by(records, lambda r: r.hard_case or "none"),
    )


def bootstrap_interval(
    records: Sequence[CaseRecord],
    statistic: Callable[[Sequence[CaseRecord]], float | None],
    resamples: int,
    seed: int = BOOTSTRAP_SEED,
) -> Interval:
    """95% percentile interval over cases (resamples with an undefined statistic are skipped)."""
    estimate = statistic(records)
    if not records or estimate is None or resamples <= 0:
        return Interval(estimate=estimate, low=None, high=None)
    rng = random.Random(seed)  # noqa: S311 - resampling, not security
    n = len(records)
    values = []
    for _ in range(resamples):
        value = statistic([records[rng.randrange(n)] for _ in range(n)])
        if value is not None:
            values.append(value)
    return Interval(estimate=estimate, **_percentiles(values))


def paired_difference(
    full: Sequence[CaseRecord],
    other: Sequence[CaseRecord],
    statistic: Callable[[Sequence[CaseRecord]], float | None],
    resamples: int,
    seed: int = BOOTSTRAP_SEED,
) -> Interval:
    """Interval of statistic(full) - statistic(other) on the same resampled cases."""
    by_id = {r.case_id: r for r in other}
    pairs = [(f, by_id[f.case_id]) for f in full if f.case_id in by_id]
    a, b = statistic([p[0] for p in pairs]), statistic([p[1] for p in pairs])
    estimate = a - b if a is not None and b is not None else None
    if estimate is None or resamples <= 0:
        return Interval(estimate=estimate, low=None, high=None)
    rng = random.Random(seed)  # noqa: S311 - resampling, not security
    values = []
    for _ in range(resamples):
        sample = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        x, y = statistic([p[0] for p in sample]), statistic([p[1] for p in sample])
        if x is not None and y is not None:
            values.append(x - y)
    return Interval(estimate=estimate, **_percentiles(values))


def paired_differences(results: Sequence[SystemResult], resamples: int) -> list[PairedDifference]:
    full = next((r for r in results if r.system == FULL_SYSTEM), None)
    if full is None:
        return []
    return [
        PairedDifference(
            other=r.system,
            accuracy=paired_difference(full.cases, r.cases, STATISTICS["accuracy"], resamples),
            false_acceptance_rate=paired_difference(
                full.cases, r.cases, STATISTICS["false_acceptance_rate"], resamples
            ),
        )
        for r in results
        if r.system != FULL_SYSTEM
    ]


def youden_on_dev(score: Callable[[BenchmarkCase], float], dev: Sequence[BenchmarkCase]) -> float:
    return tune_threshold_youden(
        [score(c) for c in dev], [c.fixture.meta.expected_verdict for c in dev]
    )


def _metrics(records: Sequence[CaseRecord]) -> Metrics:
    return compute_metrics([(r.expected, r.predicted) for r in records])


def _percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"low": None, "high": None}
    values.sort()
    return {
        "low": values[int(0.025 * (len(values) - 1))],
        "high": values[int(0.975 * (len(values) - 1))],
    }


def _accuracy_by(
    records: Sequence[CaseRecord], key: Callable[[CaseRecord], str]
) -> dict[str, float]:
    groups: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        groups[key(r)].append(r.predicted == r.expected)
    return {k: sum(v) / len(v) for k, v in sorted(groups.items())}


def verdict_counts(records: Sequence[CaseRecord]) -> dict[str, int]:
    return dict(Counter(r.predicted.value for r in records))
