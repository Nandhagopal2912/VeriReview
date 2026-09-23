"""Requirement-understanding evidence: what was asked, and how clearly (Phase 4)."""

from verireview.contracts import Evidence, EvidenceSource, ReviewCase, ReviewRequirement
from verireview.requirements import AMBIGUITY_THRESHOLD


def requirement_evidence(case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
    if not requirement.actionable:
        summary = "The comment asks for no change."
    else:
        listed = ", ".join(f"{r.id} {r.category.value}" for r in requirement.requirements)
        summary = f"Extracted {len(requirement.requirements)} requirement(s): {listed}."
    items = [
        Evidence(
            id="?",
            requirement_id=None,
            source=EvidenceSource.SEMANTIC,
            kind="requirements_extracted",
            passed=None,
            detail=summary,
            no_location_reason="derived from the review comment text",
        )
    ]
    score = requirement.ambiguity
    if score is not None:
        verdict = "ambiguous" if score >= AMBIGUITY_THRESHOLD else "clear enough to verify"
        reasons = (
            f": {'; '.join(requirement.ambiguity_reasons)}" if requirement.ambiguity_reasons else ""
        )
        items.append(
            Evidence(
                id="?",
                requirement_id=None,
                source=EvidenceSource.SEMANTIC,
                kind="requirement_ambiguity",
                passed=None,
                detail=f"Request is {verdict} (ambiguity {score:.2f}, threshold "
                f"{AMBIGUITY_THRESHOLD:.2f}){reasons}.",
                no_location_reason="derived from the review comment text",
            )
        )
    return items
