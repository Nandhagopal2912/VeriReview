import pytest

from helpers.cases import make_case
from verireview.contracts import (
    Confidence,
    Evidence,
    EvidenceSource,
    Requirement,
    RequirementCategory,
    ReviewCase,
    ReviewRequirement,
    Verdict,
    WindowFlag,
)
from verireview.verification.pipeline import Aggregator, Decision
from verireview.verification.reliability import reliability_adjusted

REQ = ReviewRequirement(
    case_id="c",
    target_file="m.py",
    requirements=[Requirement(id="R1", category=RequirementCategory.NAMING, description="d")],
    ambiguity=0.0,
    source="extracted",
)


def fixed(confidence: Confidence) -> Aggregator:
    def aggregate(case: ReviewCase, req: ReviewRequirement, ev: list[Evidence]) -> Decision:
        return Decision(Verdict.SATISFIED, confidence, [], notes=["base"])

    return aggregate


def case_with(*flags: WindowFlag) -> ReviewCase:
    case = make_case("x = 1\n", "x = 2\n", 1)
    return case.model_copy(update={"window": case.window.model_copy(update={"flags": list(flags)})})


def test_clean_case_keeps_confidence() -> None:
    decision = reliability_adjusted(fixed(Confidence.MEDIUM))(case_with(), REQ, [])

    assert decision.confidence == Confidence.MEDIUM
    assert decision.notes == ["base"]


@pytest.mark.parametrize(
    "flag",
    [WindowFlag.HISTORY_REWRITTEN, WindowFlag.BEFORE_CODE_UNAVAILABLE, WindowFlag.ANCHOR_NOT_FOUND],
)
def test_unreliable_window_lowers_confidence_with_a_reason(flag: WindowFlag) -> None:
    decision = reliability_adjusted(fixed(Confidence.MEDIUM))(case_with(flag), REQ, [])

    assert decision.confidence == Confidence.LOW
    assert decision.notes[-1].startswith("Confidence lowered:")
    assert decision.verdict == Verdict.SATISFIED  # verdict untouched


def test_benign_flags_do_not_lower_confidence() -> None:
    case = case_with(WindowFlag.RESOLUTION_TIME_UNKNOWN, WindowFlag.PRE_COMMENT_COMMITS_EXCLUDED)

    assert reliability_adjusted(fixed(Confidence.MEDIUM))(case, REQ, []).confidence == (
        Confidence.MEDIUM
    )


def test_parse_errors_lower_confidence() -> None:
    parse_error = Evidence(
        id="E1",
        requirement_id=None,
        source=EvidenceSource.AST,
        kind="parse_error",
        passed=None,
        detail="d",
        no_location_reason="r",
    )

    decision = reliability_adjusted(fixed(Confidence.MEDIUM))(case_with(), REQ, [parse_error])

    assert decision.confidence == Confidence.LOW


def test_borderline_ambiguity_lowers_confidence() -> None:
    borderline = REQ.model_copy(update={"ambiguity": 0.3})

    decision = reliability_adjusted(fixed(Confidence.MEDIUM))(case_with(), borderline, [])

    assert decision.confidence == Confidence.LOW
    assert "not fully clear" in decision.notes[-1]


def test_never_raises_confidence() -> None:
    decision = reliability_adjusted(fixed(Confidence.LOW))(case_with(), REQ, [])

    assert decision.confidence == Confidence.LOW
