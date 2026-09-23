"""Confidence from evidence reliability (Phase 8a).

Wraps an aggregator and lowers its confidence to LOW when the *case itself* is unreliable,
whatever the rules concluded. It never raises confidence. Each reason is recorded as a note.

Reasons for LOW:
- the resolution window is shaky: history rewritten, commits ordered by timestamp, the
  reviewed file or the commented line could not be located, the commit list is truncated, or
  changed files come from the whole PR (Phase 1 flags; seen on 7/8 real PRs in the live check)
- the parser reported syntax errors (structure may be incomplete)
- the request is borderline ambiguous (below the UNCERTAIN threshold, but not clear)

HIGH is never produced: it becomes available only after calibration on a frozen test set
(plan §15, Phase 10).
"""

from verireview.contracts import (
    Confidence,
    Evidence,
    ReviewCase,
    ReviewRequirement,
    WindowFlag,
)
from verireview.requirements import AMBIGUITY_THRESHOLD
from verireview.verification.pipeline import Aggregator, Decision

UNRELIABLE_WINDOW = {
    WindowFlag.HISTORY_REWRITTEN: "history was rewritten after the comment",
    WindowFlag.ORDERED_BY_TIMESTAMP: "commits were ordered by timestamp, not by the PR",
    WindowFlag.AMBIGUOUS_REWRITTEN_COMMITS: "some commits may be rebased old work or amendments",
    WindowFlag.BEFORE_CODE_UNAVAILABLE: "the reviewed version of the file is unavailable",
    WindowFlag.ANCHOR_NOT_FOUND: "the commented line could not be located",
    WindowFlag.COMMIT_LIST_TRUNCATED: "the PR's commit list is truncated",
    WindowFlag.CHANGED_FILES_FROM_WHOLE_PR: "changed files cover the whole PR, not the window",
}
BORDERLINE_AMBIGUITY = AMBIGUITY_THRESHOLD / 2


def reliability_adjusted(inner: Aggregator) -> Aggregator:
    def aggregate(
        case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
    ) -> Decision:
        decision = inner(case, requirement, evidence)
        reasons = unreliability_reasons(case, requirement, evidence)
        if not reasons or decision.confidence == Confidence.LOW:
            return decision
        return Decision(
            decision.verdict,
            Confidence.LOW,
            decision.per_requirement,
            [*decision.notes, "Confidence lowered: " + "; ".join(reasons) + "."],
        )

    return aggregate


def unreliability_reasons(
    case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
) -> list[str]:
    reasons = [text for flag, text in UNRELIABLE_WINDOW.items() if flag in case.window.flags]
    if any(e.kind == "parse_error" for e in evidence):
        reasons.append("the parser reported syntax errors")
    score = requirement.ambiguity or 0.0
    if BORDERLINE_AMBIGUITY <= score < AMBIGUITY_THRESHOLD:
        reasons.append(f"the request is not fully clear (ambiguity {score:.2f})")
    return reasons
