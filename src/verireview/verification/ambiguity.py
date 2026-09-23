"""Ambiguity gate: an unclear request cannot be verified, so it goes to a human (plan §4).

Wraps any aggregator: when the request asks for nothing or its ambiguity score reaches the
threshold, the verdict is UNCERTAIN regardless of what the code did; otherwise the wrapped
aggregator decides.
"""

from verireview.contracts import (
    Confidence,
    Evidence,
    RequirementStatus,
    ReviewCase,
    ReviewRequirement,
    Verdict,
)
from verireview.requirements import AMBIGUITY_THRESHOLD
from verireview.verification.pipeline import Aggregator, Decision


def ambiguity_gate(inner: Aggregator) -> Aggregator:
    def aggregate(
        case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
    ) -> Decision:
        score = requirement.ambiguity or 0.0
        if requirement.actionable and score < AMBIGUITY_THRESHOLD:
            return inner(case, requirement, evidence)
        why = (
            "the comment asks for no change"
            if not requirement.actionable
            else "the request is ambiguous (" + "; ".join(requirement.ambiguity_reasons) + ")"
        )
        cited = [
            e.id for e in evidence if e.kind in ("requirements_extracted", "requirement_ambiguity")
        ]
        statuses = [
            RequirementStatus(requirement_id=r.id, status=Verdict.UNCERTAIN, evidence_ids=cited)
            for r in requirement.requirements
        ]
        return Decision(
            Verdict.UNCERTAIN,
            Confidence.LOW,
            statuses,
            notes=[f"Not verified because {why}; a human should confirm what was asked."],
        )

    return aggregate
