import pytest

from helpers.cases import make_case
from verireview.contracts import (
    Confidence,
    Evidence,
    EvidenceSource,
    Requirement,
    RequirementCategory,
    ReviewRequirement,
    Verdict,
)
from verireview.verification.rules import rule_aggregator

CASE = make_case("x = 1\n", "x = 2\n", anchor=1)


def result(rid: str, passed: bool | None) -> Evidence:
    return Evidence(
        id=f"E{rid}",
        requirement_id=rid,
        source=EvidenceSource.RULE,
        kind="rule_result",
        passed=passed,
        detail="d",
        no_location_reason="summary",
    )


def requirements(n: int) -> ReviewRequirement:
    return ReviewRequirement(
        case_id="c",
        target_file="m.py",
        requirements=[
            Requirement(id=f"R{i}", category=RequirementCategory.VALIDATION, description="d")
            for i in range(1, n + 1)
        ],
        source="extracted",
    )


@pytest.mark.parametrize(
    ("outcomes", "verdict", "confidence"),
    [
        ([True], Verdict.SATISFIED, Confidence.MEDIUM),
        ([False], Verdict.NOT_SATISFIED, Confidence.MEDIUM),
        ([True, False], Verdict.PARTIALLY_SATISFIED, Confidence.MEDIUM),
        ([None], Verdict.UNCERTAIN, Confidence.LOW),
        ([True, None], Verdict.UNCERTAIN, Confidence.LOW),
        ([False, None], Verdict.NOT_SATISFIED, Confidence.LOW),
        ([True, False, None], Verdict.PARTIALLY_SATISFIED, Confidence.LOW),
    ],
)
def test_decision_table(
    outcomes: list[bool | None], verdict: Verdict, confidence: Confidence
) -> None:
    evidence = [result(f"R{i}", p) for i, p in enumerate(outcomes, start=1)]

    decision = rule_aggregator(CASE, requirements(len(outcomes)), evidence)

    assert (decision.verdict, decision.confidence) == (verdict, confidence)
    assert [s.evidence_ids for s in decision.per_requirement] == [[e.id] for e in evidence]


def test_missing_result_for_a_requirement_is_uncertain() -> None:
    decision = rule_aggregator(CASE, requirements(2), [result("R1", True)])

    assert decision.verdict == Verdict.UNCERTAIN
    assert decision.per_requirement[1].status == Verdict.UNCERTAIN


def test_code_unavailable_is_uncertain() -> None:
    unavailable = Evidence(
        id="E9",
        requirement_id=None,
        source=EvidenceSource.AST,
        kind="code_unavailable",
        passed=None,
        detail="d",
        no_location_reason="r",
    )

    decision = rule_aggregator(CASE, requirements(1), [result("R1", True), unavailable])

    assert decision.verdict == Verdict.UNCERTAIN


def test_confidence_is_never_high() -> None:
    decision = rule_aggregator(CASE, requirements(1), [result("R1", True)])

    assert decision.confidence != Confidence.HIGH
