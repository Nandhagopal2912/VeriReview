"""Classification and operational-risk metrics (plan §20). Pure functions, no dependencies.

Conventions (match scikit-learn's ``zero_division=0``): precision/recall/F1 of a class with no
predictions or no support is 0.0. Rates with an empty denominator are None, never 0.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from verireview.contracts import Verdict

VERDICTS = list(Verdict)
INVALID_RESOLUTIONS = frozenset({Verdict.NOT_SATISFIED, Verdict.PARTIALLY_SATISFIED})


class ClassMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int


class Metrics(BaseModel):
    n: int
    accuracy: float
    macro_f1: float
    per_class: dict[Verdict, ClassMetrics]
    confusion: dict[Verdict, dict[Verdict, int]]  # confusion[gold][predicted]
    false_acceptance_rate: float | None
    false_blocking_rate: float | None


def compute_metrics(pairs: Sequence[tuple[Verdict, Verdict]]) -> Metrics:
    """``pairs`` = (gold, predicted) per case."""
    confusion = {g: {p: 0 for p in VERDICTS} for g in VERDICTS}
    for gold, predicted in pairs:
        confusion[gold][predicted] += 1

    per_class: dict[Verdict, ClassMetrics] = {}
    for v in VERDICTS:
        tp = confusion[v][v]
        predicted_v = sum(confusion[g][v] for g in VERDICTS)
        support = sum(confusion[v].values())
        precision = tp / predicted_v if predicted_v else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[v] = ClassMetrics(precision=precision, recall=recall, f1=f1, support=support)

    n = len(pairs)
    present = [m for m in per_class.values() if m.support > 0]
    return Metrics(
        n=n,
        accuracy=sum(confusion[v][v] for v in VERDICTS) / n if n else 0.0,
        macro_f1=sum(m.f1 for m in present) / len(present) if present else 0.0,
        per_class=per_class,
        confusion=confusion,
        false_acceptance_rate=false_acceptance_rate(pairs),
        false_blocking_rate=false_blocking_rate(pairs),
    )


def false_acceptance_rate(pairs: Sequence[tuple[Verdict, Verdict]]) -> float | None:
    """Invalid resolutions (gold NOT/PARTIAL) the verifier accepted as SATISFIED."""
    invalid = [p for g, p in pairs if g in INVALID_RESOLUTIONS]
    if not invalid:
        return None
    return sum(p == Verdict.SATISFIED for p in invalid) / len(invalid)


def false_blocking_rate(pairs: Sequence[tuple[Verdict, Verdict]]) -> float | None:
    """Valid resolutions (gold SATISFIED) the verifier called NOT_SATISFIED."""
    valid = [p for g, p in pairs if g == Verdict.SATISFIED]
    if not valid:
        return None
    return sum(p == Verdict.NOT_SATISFIED for p in valid) / len(valid)
