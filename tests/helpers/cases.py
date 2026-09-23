"""Minimal ReviewCase / requirement builders for evidence and pipeline tests."""

from datetime import UTC, datetime

from verireview.contracts import (
    Requirement,
    RequirementCategory,
    ResolutionWindow,
    ReviewCase,
    ReviewRequirement,
    ReviewThread,
    ThreadComment,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)

REQUIREMENT = ReviewRequirement(
    case_id="c",
    target_file="m.py",
    requirements=[Requirement(id="R1", category=RequirementCategory.OTHER, description="fix")],
    source="stub",
)


def make_case(
    before: str | None,
    after: str | None,
    anchor: int | None = 5,
    tests: dict[str, str] | None = None,
) -> ReviewCase:
    return ReviewCase(
        case_id="c",
        repository="r/r",
        pull_number=1,
        pull_title="t",
        base_sha="a",
        head_sha="b",
        thread=ReviewThread(
            root_comment_id=1,
            path="m.py",
            line=anchor,
            original_line=anchor,
            diff_hunk="@@",
            original_commit_sha="a",
            commit_sha="b",
            comments=[ThreadComment(id=1, author="r", body="fix", created_at=NOW)],
            is_resolved=True,
        ),
        window=ResolutionWindow(start_commit_sha="a", end_commit_sha="b", subsequent_commits=[]),
        file_path="m.py",
        before_code=before,
        anchor_line=anchor,
        after_code=after,
        unified_diff="",
        changed_files=[],
        test_files=tests or {},
        ingested_at=NOW,
    )
