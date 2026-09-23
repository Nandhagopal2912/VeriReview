"""Phase 2 preliminary aggregator: the naive "changed near the comment ⇒ satisfied" baseline.

This is deliberately the approach the plan warns against. It exists as the floor that every
later phase must measurably beat. Decision table (first match wins):

    code or anchor unavailable                   → UNCERTAIN      LOW
    change near the commented line, or tests     → SATISFIED      LOW
    file changed, but not near the comment       → NOT_SATISFIED  LOW
    nothing changed                              → NOT_SATISFIED  MEDIUM

Confidence is never HIGH: locality says nothing about whether the change does what was asked.
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

BASELINE_NOTE = (
    "Preliminary locality baseline: checks where code changed, not whether the change "
    "satisfies the request (semantic checks arrive in Phases 3-5)."
)


def locality_aggregator(
    case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
) -> Decision:
    facts = {e.kind: e for e in evidence}

    if "code_unavailable" in facts:
        verdict, confidence = Verdict.UNCERTAIN, Confidence.LOW
    elif _passed(facts, "change_near_target") or _passed(facts, "tests_changed"):
        verdict, confidence = Verdict.SATISFIED, Confidence.LOW
    elif _passed(facts, "file_changed"):
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
    return Decision(verdict, confidence, statuses, notes=[BASELINE_NOTE])


def _passed(facts: dict[str, Evidence], kind: str) -> bool:
    return kind in facts and facts[kind].passed is True
