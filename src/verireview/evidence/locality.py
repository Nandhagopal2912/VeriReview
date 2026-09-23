"""Change-locality evidence (Phase 2 baseline): did anything change, and near the comment?

Text-level only. It knows nothing about symbols or semantics; Phase 3 replaces the fixed
line radius with the enclosing function/symbol from Tree-sitter.
"""

from verireview.contracts import (
    CodeLocation,
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
)
from verireview.diff import Change, changes
from verireview.evidence.tests import changed_tests_evidence

NEAR_TARGET_RADIUS = 10

__all__ = ["NEAR_TARGET_RADIUS", "Change", "change_locality_evidence", "changes"]


def change_locality_evidence(case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
    if case.before_code is None or case.after_code is None or case.anchor_line is None:
        return [
            Evidence(
                id="?",
                requirement_id=None,
                source=EvidenceSource.DIFF,
                kind="code_unavailable",
                passed=None,
                detail="Before/after code or the commented line is unavailable.",
                no_location_reason="missing before_code, after_code or anchor_line",
            )
        ]

    found = changes(case.before_code, case.after_code)
    anchor = case.anchor_line
    first, last = max(1, anchor - NEAR_TARGET_RADIUS), anchor + NEAR_TARGET_RADIUS
    near = [c for c in found if c.touches(first, last)]
    evidence = [_file_changed(case, found)]

    if near:
        closest = min(near, key=lambda c: abs(c.b_start + 1 - anchor))
        evidence.append(
            Evidence(
                id="?",
                requirement_id="R1",
                source=EvidenceSource.DIFF,
                kind="change_near_target",
                passed=True,
                detail=(
                    f"Code changed within {NEAR_TARGET_RADIUS} lines of the commented "
                    f"line {anchor}."
                ),
                location=_after_location(case, closest),
            )
        )
    else:
        before_len = len(case.before_code.split("\n"))
        evidence.append(
            Evidence(
                id="?",
                requirement_id="R1",
                source=EvidenceSource.DIFF,
                kind="change_near_target",
                passed=False,
                detail=(
                    f"No change within {NEAR_TARGET_RADIUS} lines of the commented line {anchor}."
                ),
                location=CodeLocation(
                    file=case.thread.path,
                    line_start=first,
                    line_end=min(last, before_len),
                    version="before",
                ),
            )
        )

    evidence.extend(changed_tests_evidence(case, requirement))
    return evidence


def _file_changed(case: ReviewCase, found: list[Change]) -> Evidence:
    if not found:
        return Evidence(
            id="?",
            requirement_id=None,
            source=EvidenceSource.DIFF,
            kind="file_changed",
            passed=False,
            detail="The commented file did not change after the comment.",
            no_location_reason="file identical before and after",
        )
    return Evidence(
        id="?",
        requirement_id=None,
        source=EvidenceSource.DIFF,
        kind="file_changed",
        passed=True,
        detail=f"The commented file changed in {len(found)} region(s).",
        location=_after_location(case, found[0], last=found[-1]),
    )


def _after_location(case: ReviewCase, change: Change, last: Change | None = None) -> CodeLocation:
    """After-side span of a change; pure deletions point at the line where code was removed."""
    end_change = last or change
    start = change.a_start + 1
    end = max(start, end_change.a_end)
    return CodeLocation(file=case.file_path, line_start=start, line_end=end, version="after")
