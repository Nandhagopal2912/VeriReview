"""Phase 3 aggregator: "the commented function's *code* changed ⇒ satisfied".

Same idea as the Phase 2 baseline, but scoped to the enclosing symbol (not a line radius) and
blind to comments, docstrings and formatting. Still a baseline: it does not check *what*
changed. Decision table (first match wins):

    code or anchor unavailable                        → UNCERTAIN      LOW
    target symbol changed structurally, or tests      → SATISFIED      LOW
    file's code changed, but not the target           → NOT_SATISFIED  LOW
    no code changed (at most comments/formatting)     → NOT_SATISFIED  MEDIUM
"""

from verireview.contracts import (
    Confidence,
    Evidence,
    RequirementStatus,
    ReviewCase,
    ReviewRequirement,
    Verdict,
)
from verireview.verification.pipeline import Decision

STRUCTURAL_NOTE = (
    "Structural baseline: checks whether the commented function's code changed (ignoring "
    "comments, docstrings and formatting), not whether the change satisfies the request "
    "(rules arrive in Phase 5)."
)


def structural_aggregator(
    case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
) -> Decision:
    facts = {e.kind: e for e in evidence}

    if "code_unavailable" in facts:
        verdict, confidence = Verdict.UNCERTAIN, Confidence.LOW
    elif _passed(facts, "target_changed_structurally") or _passed(facts, "tests_changed"):
        verdict, confidence = Verdict.SATISFIED, Confidence.LOW
    elif _passed(facts, "file_changed_structurally"):
        verdict, confidence = Verdict.NOT_SATISFIED, Confidence.LOW
    else:
        verdict, confidence = Verdict.NOT_SATISFIED, Confidence.MEDIUM

    statuses = [
        RequirementStatus(
            requirement_id=r.id,
            status=verdict,
            evidence_ids=[e.id for e in evidence if e.requirement_id in (r.id, None)],
        )
        for r in requirement.requirements
    ]
    return Decision(verdict, confidence, statuses, notes=[STRUCTURAL_NOTE])


def _passed(facts: dict[str, Evidence], kind: str) -> bool:
    return kind in facts and facts[kind].passed is True
