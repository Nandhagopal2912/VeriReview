import pytest
from pydantic import ValidationError

from verireview.contracts import (
    CodeLocation,
    Confidence,
    Evidence,
    EvidenceSource,
    Requirement,
    RequirementCategory,
    RequirementStatus,
    ReviewRequirement,
    Verdict,
    VerificationResult,
)

LOCATION = CodeLocation(file="a.py", line_start=3, line_end=4, version="after")


def evidence(eid: str = "E1", **overrides: object) -> Evidence:
    fields: dict[str, object] = {
        "id": eid,
        "requirement_id": "R1",
        "source": EvidenceSource.DIFF,
        "kind": "k",
        "passed": True,
        "detail": "d",
        "location": LOCATION,
    }
    fields.update(overrides)
    return Evidence.model_validate(fields)


def result(evidence_items: list[Evidence], cited: list[str]) -> VerificationResult:
    return VerificationResult(
        case_id="c",
        verdict=Verdict.SATISFIED,
        confidence=Confidence.LOW,
        per_requirement=[
            RequirementStatus(requirement_id="R1", status=Verdict.SATISFIED, evidence_ids=cited)
        ],
        evidence=evidence_items,
        explanation="x",
        pipeline_version="test",
    )


def test_evidence_needs_a_location_or_a_reason() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        evidence(location=None)


def test_evidence_cannot_have_both_location_and_reason() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        evidence(no_location_reason="because")


def test_evidence_with_reason_only_is_valid() -> None:
    assert evidence(location=None, no_location_reason="no tests").location is None


def test_location_lines_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        CodeLocation(file="a.py", line_start=5, line_end=4, version="after")


def test_result_rejects_citation_of_unknown_evidence() -> None:
    with pytest.raises(ValidationError, match="unknown"):
        result([evidence("E1")], cited=["E2"])


def test_result_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        result([evidence("E1"), evidence("E1")], cited=["E1"])


def test_valid_result() -> None:
    assert result([evidence("E1")], cited=["E1"]).verdict == Verdict.SATISFIED


def test_review_requirement_needs_at_least_one_requirement() -> None:
    with pytest.raises(ValidationError):
        ReviewRequirement(case_id="c", target_file="a.py", requirements=[], source="manual")


def test_ambiguity_is_bounded() -> None:
    req = Requirement(id="R1", category=RequirementCategory.NAMING, description="d")
    with pytest.raises(ValidationError):
        ReviewRequirement(
            case_id="c", target_file="a.py", requirements=[req], ambiguity=1.5, source="manual"
        )
