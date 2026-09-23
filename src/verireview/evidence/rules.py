"""Rule evidence (Phase 5): run the category rule for every requirement.

Emits each rule's own evidence plus one ``rule_result`` item per requirement (passed: True =
satisfied, False = not satisfied, None = inconclusive) that the aggregator reads.
"""

from verireview.contracts import (
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
)
from verireview.rules import RuleContext, RuleStatus, check_requirement

_PASSED = {
    RuleStatus.SATISFIED: True,
    RuleStatus.NOT_SATISFIED: False,
    RuleStatus.INCONCLUSIVE: None,
}


def rule_evidence(case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
    ctx = RuleContext.build(case, requirement)
    if ctx is None:
        return []  # the structural stage already reports code_unavailable
    items: list[Evidence] = []
    for req in requirement.requirements:
        outcome = check_requirement(req, ctx)
        items += outcome.evidence
        anchor = next((e.location for e in outcome.evidence if e.location), None)
        items.append(
            Evidence(
                id="?",
                requirement_id=req.id,
                source=EvidenceSource.RULE,
                kind="rule_result",
                passed=_PASSED[outcome.status],
                detail=f"{req.id} ({req.category.value}) {outcome.status.value}: "
                f"{outcome.summary}"
                + (" Already present before the comment." if outcome.already_present else ""),
                location=anchor,
                no_location_reason=None if anchor else "summary of the rule's evidence",
            )
        )
    return items
