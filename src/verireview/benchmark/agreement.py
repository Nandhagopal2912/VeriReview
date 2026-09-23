"""Inter-annotator agreement and gold labels (docs/annotation_guide.md §7).

Agreement, over the cases both annotators labelled:
- inclusion: observed agreement and kappa on include / exclude
- verdict: Cohen's kappa on the 4-class verdict (cases both included)
- binary: kappa on valid (SATISFIED) vs invalid (NOT / PARTIALLY); cases either annotator
  called UNCERTAIN are left out
- per category (cases where both annotators chose the same main category)

Gold: a case both annotators agree on (same inclusion and, if included, same verdict and number of
requirements) takes annotator A's label. Every other case needs an adjudication decision.
"""

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from verireview.benchmark.labels import AnnotationFile, CaseAnnotation
from verireview.benchmark.store import GoldLabel
from verireview.contracts import Verdict

_VALID = {Verdict.SATISFIED}
_INVALID = {Verdict.NOT_SATISFIED, Verdict.PARTIALLY_SATISFIED}


class Kappa(BaseModel):
    n: int
    observed: float | None
    kappa: float | None


class Disagreement(BaseModel):
    case_id: str
    fields: list[str]
    a: CaseAnnotation
    b: CaseAnnotation


class AgreementReport(BaseModel):
    annotator_a: str
    annotator_b: str
    common: int
    only_a: list[str]
    only_b: list[str]
    inclusion: Kappa
    verdict: Kappa
    binary: Kappa
    by_category: dict[str, Kappa]
    disagreements: list[Disagreement]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    chosen: Literal["a", "b", "custom"]
    label: CaseAnnotation | None = Field(default=None, description="Required when 'custom'.")
    reason: str = Field(min_length=3)


class AdjudicationFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjudicator: str = Field(min_length=1)
    decisions: list[Decision]


class PendingAdjudicationError(ValueError):
    pass


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> Kappa:
    """Cohen's kappa for two raters. None when undefined (no items, or chance agreement = 1)."""
    if len(a) != len(b):
        raise ValueError("rating lists differ in length")
    n = len(a)
    if n == 0:
        return Kappa(n=0, observed=None, kappa=None)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    return Kappa(n=n, observed=observed, kappa=kappa)


def disagreement_fields(a: CaseAnnotation, b: CaseAnnotation) -> list[str]:
    if a.include != b.include:
        return ["include"]
    if not a.include:
        return []  # both excluded: the reason may differ, the case is out either way
    fields = []
    if a.verdict != b.verdict:
        fields.append("verdict")
    if len(a.requirements) != len(b.requirements):
        fields.append("requirement_count")
    return fields


def agreement(a: AnnotationFile, b: AnnotationFile) -> AgreementReport:
    la, lb = a.by_case(), b.by_case()
    common = sorted(set(la) & set(lb))
    both_in = [c for c in common if la[c].include and lb[c].include]
    binary = [
        c
        for c in both_in
        if la[c].verdict in _VALID | _INVALID and lb[c].verdict in _VALID | _INVALID
    ]
    groups: dict[str, list[str]] = defaultdict(list)
    for c in both_in:
        category = la[c].category
        if category is not None and category == lb[c].category:
            groups[category.value].append(c)
    disagreements = [
        Disagreement(case_id=c, fields=fields, a=la[c], b=lb[c])
        for c in common
        if (fields := disagreement_fields(la[c], lb[c]))
    ]
    return AgreementReport(
        annotator_a=a.annotator,
        annotator_b=b.annotator,
        common=len(common),
        only_a=sorted(set(la) - set(lb)),
        only_b=sorted(set(lb) - set(la)),
        inclusion=cohen_kappa(
            [str(la[c].include) for c in common], [str(lb[c].include) for c in common]
        ),
        verdict=_verdict_kappa(both_in, la, lb),
        binary=cohen_kappa(
            [str(la[c].verdict in _VALID) for c in binary],
            [str(lb[c].verdict in _VALID) for c in binary],
        ),
        by_category={k: _verdict_kappa(v, la, lb) for k, v in sorted(groups.items())},
        disagreements=disagreements,
    )


def build_gold(
    a: AnnotationFile, b: AnnotationFile, adjudication: AdjudicationFile | None = None
) -> dict[str, GoldLabel]:
    """Gold for every case both annotated. Raises if a disagreement has no decision."""
    report = agreement(a, b)
    la, lb = a.by_case(), b.by_case()
    decisions = {d.case_id: d for d in (adjudication.decisions if adjudication else [])}
    disputed = {d.case_id for d in report.disagreements}
    pending = sorted(disputed - set(decisions))
    if pending:
        raise PendingAdjudicationError(f"{len(pending)} disagreement(s) need a decision: {pending}")
    annotators = [a.annotator, b.annotator]
    gold: dict[str, GoldLabel] = {}
    for case_id in sorted(set(la) & set(lb)):
        if case_id not in disputed:
            gold[case_id] = GoldLabel(label=la[case_id], annotators=annotators, agreed=True)
            continue
        decision = decisions[case_id]
        label = {"a": la[case_id], "b": lb[case_id]}.get(decision.chosen) or decision.label
        if label is None:
            raise ValueError(f"{case_id}: a 'custom' decision needs a label")
        gold[case_id] = GoldLabel(
            label=label.model_copy(update={"case_id": case_id}),
            annotators=annotators,
            agreed=False,
            adjudicator=adjudication.adjudicator if adjudication else None,
            adjudication_reason=decision.reason,
        )
    return gold


def _verdict_kappa(
    cases: list[str], la: dict[str, CaseAnnotation], lb: dict[str, CaseAnnotation]
) -> Kappa:
    return cohen_kappa([str(la[c].verdict) for c in cases], [str(lb[c].verdict) for c in cases])
