from helpers.github import C1, C2, C3, C4, gh_comment, gh_commit, ts
from verireview.contracts import CommitRef, ReviewThread, WindowFlag
from verireview.gh.api import PR_COMMITS_LIMIT
from verireview.ingestion import build_window
from verireview.threads import reconstruct_threads

COMMENT_AT = "2026-01-01T12:00:00Z"
COMMITS = [
    gh_commit(C1, "2026-01-01T10:00:00Z"),
    gh_commit(C2, "2026-01-01T11:00:00Z"),
    gh_commit(C3, "2026-01-01T13:00:00Z"),
    gh_commit(C4, "2026-01-01T14:00:00Z"),
]


def thread_on(commit: str = C2, resolved: bool | None = True) -> ReviewThread:
    (thread,) = reconstruct_threads([gh_comment(1, COMMENT_AT, original_commit_id=commit)])
    return thread.model_copy(update={"is_resolved": resolved})


def shas(commits: list[CommitRef]) -> list[str]:
    return [c.sha for c in commits]


def test_commits_after_reviewed_commit_are_candidates() -> None:
    window = build_window(thread_on(C2), COMMITS)

    assert window.start_commit_sha == C2
    assert window.end_commit_sha == C4
    assert shas(window.subsequent_commits) == [C3, C4]
    assert window.flags == [WindowFlag.RESOLUTION_TIME_UNKNOWN]


def test_commits_pushed_before_the_comment_are_excluded() -> None:
    # Reviewer looked at C1, but C2 was committed before the comment was written.
    window = build_window(thread_on(C1), COMMITS)

    assert shas(window.subsequent_commits) == [C3, C4]
    assert shas(window.excluded_pre_comment_commits) == [C2]
    assert WindowFlag.PRE_COMMENT_COMMITS_EXCLUDED in window.flags


def test_no_commits_after_comment() -> None:
    window = build_window(thread_on(C4), COMMITS)

    assert window.subsequent_commits == []
    assert window.end_commit_sha == window.start_commit_sha == C4
    assert WindowFlag.NO_SUBSEQUENT_COMMITS in window.flags


def test_force_push_falls_back_to_timestamps() -> None:
    rewritten = [
        gh_commit("a" * 40, "2026-01-01T10:00:00Z"),
        gh_commit("b" * 40, "2026-01-01T13:00:00Z"),
    ]

    window = build_window(thread_on(C2), rewritten, force_pushed_at=[ts("2026-01-01T12:45:00Z")])

    assert shas(window.subsequent_commits) == ["b" * 40]
    assert window.start_commit_sha == C2
    assert {
        WindowFlag.ORIGINAL_COMMIT_NOT_IN_PR,
        WindowFlag.HISTORY_REWRITTEN,
        WindowFlag.ORDERED_BY_TIMESTAMP,
    } <= set(window.flags)


def test_rebase_keeps_old_work_out_of_the_responses() -> None:
    # Pattern from pallets/click#2622: a rebase after the comment re-commits everything, so
    # committer dates are all "after"; author dates still show which work predates the comment.
    rebased = [
        gh_commit("a" * 40, "2026-01-02T09:00:00Z", authored_at="2025-12-01T10:00:00Z"),
        gh_commit("b" * 40, "2026-01-02T09:00:00Z", authored_at="2026-01-01T15:00:00Z"),
        gh_commit("c" * 40, "2026-01-02T10:00:00Z"),
    ]

    window = build_window(thread_on(C2), rebased, force_pushed_at=[ts("2026-01-02T09:05:00Z")])

    assert shas(window.subsequent_commits) == ["b" * 40, "c" * 40]
    assert shas(window.ambiguous_rewritten_commits) == ["a" * 40]
    assert window.end_commit_sha == "c" * 40
    assert WindowFlag.AMBIGUOUS_REWRITTEN_COMMITS in window.flags


def test_amended_response_is_ambiguous_but_still_ends_the_window() -> None:
    # Pattern from pallets/click#3460: one commit amended after the comment keeps its old
    # author date. It may contain the response, so the "after" state must still be that commit.
    amended = [gh_commit("d" * 40, "2026-01-03T10:00:00Z", authored_at="2025-12-30T10:00:00Z")]

    window = build_window(thread_on(C2), amended, force_pushed_at=[ts("2026-01-03T10:01:00Z")])

    assert window.subsequent_commits == []
    assert shas(window.ambiguous_rewritten_commits) == ["d" * 40]
    assert window.end_commit_sha == "d" * 40
    assert WindowFlag.NO_SUBSEQUENT_COMMITS in window.flags


def test_ambiguity_only_applies_when_history_was_rewritten() -> None:
    # Reviewed commit is present: a commit authored earlier but pushed later is a normal
    # candidate (committed after the comment), not ambiguous.
    commits = [
        *COMMITS[:2],
        gh_commit(C3, "2026-01-01T13:00:00Z", authored_at="2026-01-01T11:30:00Z"),
    ]

    window = build_window(thread_on(C2), commits)

    assert shas(window.subsequent_commits) == [C3]
    assert window.ambiguous_rewritten_commits == []


def test_missing_commit_without_force_push_is_not_called_a_rewrite() -> None:
    window = build_window(thread_on("f" * 40), COMMITS)

    assert WindowFlag.ORIGINAL_COMMIT_NOT_IN_PR in window.flags
    assert WindowFlag.HISTORY_REWRITTEN not in window.flags


def test_force_push_before_comment_is_not_a_rewrite_of_reviewed_history() -> None:
    window = build_window(
        thread_on("f" * 40), COMMITS, force_pushed_at=[ts("2026-01-01T09:00:00Z")]
    )

    assert WindowFlag.HISTORY_REWRITTEN not in window.flags


def test_unknown_resolution_state_is_flagged() -> None:
    window = build_window(thread_on(C2, resolved=None), COMMITS)

    assert WindowFlag.RESOLUTION_STATE_UNKNOWN in window.flags
    assert WindowFlag.RESOLUTION_TIME_UNKNOWN not in window.flags


def test_open_thread_has_no_resolution_flags() -> None:
    window = build_window(thread_on(C2, resolved=False), COMMITS)

    assert window.flags == []


def test_commit_without_committer_date_is_kept() -> None:
    commits = [*COMMITS[:2], gh_commit(C3, None)]

    window = build_window(thread_on(C2), commits)

    assert shas(window.subsequent_commits) == [C3]


def test_commit_list_at_api_cap_is_flagged_truncated() -> None:
    many = [gh_commit(f"{i:040x}", "2026-01-01T13:00:00Z") for i in range(PR_COMMITS_LIMIT)]

    window = build_window(thread_on(many[0].sha), many)

    assert WindowFlag.COMMIT_LIST_TRUNCATED in window.flags
