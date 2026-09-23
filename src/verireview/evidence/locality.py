"""Change-locality evidence (Phase 2 baseline): did anything change, and near the comment?

Text-level only. It knows nothing about symbols or semantics; Phase 3 replaces the fixed
line radius with the enclosing function/symbol from Tree-sitter.
"""

import difflib
from dataclasses import dataclass

from verireview.contracts import (
    CodeLocation,
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
)

NEAR_TARGET_RADIUS = 10


@dataclass(frozen=True)
class Change:
    """One diff region: before lines [b_start, b_end) → after lines [a_start, a_end), 0-based."""

    b_start: int
    b_end: int
    a_start: int
    a_end: int

    def touches(self, first: int, last: int) -> bool:
        """Does the change touch 1-based before-lines ``first..last`` (inserts at a gap count)?"""
        if self.b_start == self.b_end:  # pure insertion before line b_start + 1
            return first - 1 <= self.b_start <= last
        return self.b_start < last and self.b_end >= first


def changes(before: str, after: str) -> list[Change]:
    matcher = difflib.SequenceMatcher(None, before.split("\n"), after.split("\n"), autojunk=False)
    return [
        Change(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"
    ]


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

    evidence.append(_tests_changed(case))
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


def _tests_changed(case: ReviewCase) -> Evidence:
    if not case.test_files:
        return Evidence(
            id="?",
            requirement_id=None,
            source=EvidenceSource.TEST,
            kind="tests_changed",
            passed=False,
            detail="No test files were added or changed.",
            no_location_reason="no changed test files",
        )
    path, content = next(iter(sorted(case.test_files.items())))
    return Evidence(
        id="?",
        requirement_id=None,
        source=EvidenceSource.TEST,
        kind="tests_changed",
        passed=True,
        detail=f"{len(case.test_files)} test file(s) added or changed.",
        location=CodeLocation(
            file=path, line_start=1, line_end=max(1, content.count("\n")), version="after"
        ),
    )


def _after_location(case: ReviewCase, change: Change, last: Change | None = None) -> CodeLocation:
    """After-side span of a change; pure deletions point at the line where code was removed."""
    end_change = last or change
    start = change.a_start + 1
    end = max(start, end_change.a_end)
    return CodeLocation(file=case.file_path, line_start=start, line_end=end, version="after")
