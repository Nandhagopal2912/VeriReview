from pathlib import Path

import pytest

from verireview.contracts import (
    CodeLocation,
    Confidence,
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
    Verdict,
)
from verireview.dataset import Fixture, iter_fixtures
from verireview.requirements.stub import whole_comment_requirement
from verireview.verification import PRELIMINARY_VERSION, Decision, Pipeline, preliminary_pipeline
from verireview.verification.preliminary import BASELINE_NOTE, locality_aggregator

ROOT = Path(__file__).resolve().parents[3] / "dataset" / "fixtures"
FIXTURES = list(iter_fixtures(ROOT))
LOC = CodeLocation(file="a.py", line_start=1, line_end=1, version="after")


def item(kind: str, passed: bool | None) -> Evidence:
    return Evidence(
        id=f"E-{kind}",
        requirement_id=None,
        source=EvidenceSource.DIFF,
        kind=kind,
        passed=passed,
        detail=kind,
        location=LOC,
    )


def decide(*evidence: Evidence) -> Decision:
    case = FIXTURES[0].case
    return locality_aggregator(case, whole_comment_requirement(case), list(evidence))


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ([item("code_unavailable", None)], (Verdict.UNCERTAIN, Confidence.LOW)),
        (
            [
                item("file_changed", True),
                item("change_near_target", True),
                item("tests_changed", False),
            ],
            (Verdict.SATISFIED, Confidence.LOW),
        ),
        (
            [
                item("file_changed", False),
                item("change_near_target", False),
                item("tests_changed", True),
            ],
            (Verdict.SATISFIED, Confidence.LOW),
        ),
        (
            [
                item("file_changed", True),
                item("change_near_target", False),
                item("tests_changed", False),
            ],
            (Verdict.NOT_SATISFIED, Confidence.LOW),
        ),
        (
            [
                item("file_changed", False),
                item("change_near_target", False),
                item("tests_changed", False),
            ],
            (Verdict.NOT_SATISFIED, Confidence.MEDIUM),
        ),
    ],
    ids=["unavailable", "near-change", "tests-only", "far-change", "nothing-changed"],
)
def test_decision_table(evidence: list[Evidence], expected: tuple[Verdict, Confidence]) -> None:
    decision = decide(*evidence)

    assert (decision.verdict, decision.confidence) == expected


def test_confidence_is_never_high() -> None:
    results = [preliminary_pipeline().run(f.case) for f in FIXTURES]

    assert all(r.confidence != Confidence.HIGH for r in results)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.meta.case_id)
def test_pipeline_produces_a_valid_evidence_citing_result(fixture: Fixture) -> None:
    result = preliminary_pipeline().run(fixture.case)

    assert result.case_id == fixture.case.case_id
    assert result.pipeline_version == PRELIMINARY_VERSION
    assert [e.id for e in result.evidence] == [f"E{i}" for i in range(1, len(result.evidence) + 1)]
    cited = {eid for status in result.per_requirement for eid in status.evidence_ids}
    assert cited and cited <= {e.id for e in result.evidence}
    # Every evidence item appears in the explanation, which never states an unrecorded fact.
    for e in result.evidence:
        assert f"[{e.id}] {e.detail}" in result.explanation
    assert result.verdict.value in result.explanation
    assert BASELINE_NOTE in result.explanation


def test_pipeline_is_deterministic() -> None:
    case = FIXTURES[0].case

    assert preliminary_pipeline().run(case) == preliminary_pipeline().run(case)


def test_stages_are_pluggable() -> None:
    def always_uncertain(
        case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
    ) -> Decision:
        return Decision(Verdict.UNCERTAIN, Confidence.LOW, [])

    def one_fact(case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
        return [item("custom", None)]

    pipeline = Pipeline(
        "custom-1", whole_comment_requirement, [one_fact, one_fact], always_uncertain
    )
    result = pipeline.run(FIXTURES[0].case)

    assert result.verdict == Verdict.UNCERTAIN
    assert [e.id for e in result.evidence] == ["E1", "E2"]  # renumbered by the pipeline


def test_stub_requirement_wraps_whole_comment() -> None:
    case = FIXTURES[0].case
    requirement = whole_comment_requirement(case)

    assert requirement.source == "stub"
    assert [r.description for r in requirement.requirements] == [case.thread.root.body]
