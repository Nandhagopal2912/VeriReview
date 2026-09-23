"""Phase 5 aggregator: combine per-requirement rule results into a verdict.

Per requirement (from its ``rule_result``): satisfied → SATISFIED, not satisfied →
NOT_SATISFIED, inconclusive (or no result) → UNCERTAIN.

Overall (first match wins):

    code unavailable, or no rule results            → UNCERTAIN            LOW
    some NOT and some SATISFIED                     → PARTIALLY_SATISFIED
    some NOT, none SATISFIED                        → NOT_SATISFIED
    any UNCERTAIN (and no NOT)                      → UNCERTAIN            LOW
    all SATISFIED                                   → SATISFIED

Confidence: LOW when anything is inconclusive; otherwise MEDIUM. It is never HIGH until the
rules are evaluated and calibrated on a frozen test set (plan §15, Phase 10). ADR-001: an
``already_present`` result keeps SATISFIED at most MEDIUM (already the ceiling here).
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

_STATUS = {True: Verdict.SATISFIED, False: Verdict.NOT_SATISFIED, None: Verdict.UNCERTAIN}


def rule_aggregator(
    case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
) -> Decision:
    results = {e.requirement_id: e for e in evidence if e.kind == "rule_result"}
    unavailable = any(e.kind == "code_unavailable" for e in evidence)

    statuses = []
    for r in requirement.requirements:
        result = results.get(r.id)
        status = Verdict.UNCERTAIN if unavailable or result is None else _STATUS[result.passed]
        cited = [e.id for e in evidence if e.requirement_id == r.id]
        statuses.append(RequirementStatus(requirement_id=r.id, status=status, evidence_ids=cited))

    found = {s.status for s in statuses}
    if unavailable or not results:
        verdict, confidence = Verdict.UNCERTAIN, Confidence.LOW
    elif Verdict.NOT_SATISFIED in found and Verdict.SATISFIED in found:
        verdict, confidence = Verdict.PARTIALLY_SATISFIED, _confidence(found)
    elif Verdict.NOT_SATISFIED in found:
        verdict, confidence = Verdict.NOT_SATISFIED, _confidence(found)
    elif Verdict.UNCERTAIN in found:
        verdict, confidence = Verdict.UNCERTAIN, Confidence.LOW
    else:
        verdict, confidence = Verdict.SATISFIED, Confidence.MEDIUM

    notes = []
    if any(e.kind == "already_present" for e in evidence):
        notes.append("Part of the request was already met before the comment (ADR-001).")
    return Decision(verdict, confidence, statuses, notes)


def _confidence(found: set[Verdict]) -> Confidence:
    return Confidence.LOW if Verdict.UNCERTAIN in found else Confidence.MEDIUM
