"""Test-change evidence: were test files added or changed in the resolution window?

Whether a test exercises the requested case is a rule-level question (Phase 5).
"""

from verireview.contracts import (
    CodeLocation,
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
)


def changed_tests_evidence(case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
    if not case.test_files:
        return [
            Evidence(
                id="?",
                requirement_id=None,
                source=EvidenceSource.TEST,
                kind="tests_changed",
                passed=False,
                detail="No test files were added or changed.",
                no_location_reason="no changed test files",
            )
        ]
    path, content = next(iter(sorted(case.test_files.items())))
    return [
        Evidence(
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
    ]
