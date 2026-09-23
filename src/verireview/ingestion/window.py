"""Temporal review-resolution window (plan §6).

Which commits could be a response to the review comment?

1. Locate the reviewed commit (``original_commit_sha``) in the PR's ordered commit list.
   Every later commit is a candidate.
2. If it is not in the list (force-push/rebase, or the 250-commit API cap), fall back to
   committer timestamps and flag the window as less reliable.
3. Candidates committed *before* the comment was written cannot be responses to it (the
   reviewer was looking at an older commit), so they are excluded and reported separately.
4. GitHub exposes whether a thread is resolved but not *when*, so the window ends at the PR
   head, flagged ``RESOLUTION_TIME_UNKNOWN``. Webhook events (Phase 11) will give the exact time.

This module is pure: no I/O, fully deterministic.
"""

from collections.abc import Sequence
from datetime import datetime

from  CommitRef, ResolutionWindow, ReviewThread, WindowFverireview.contracts importlag
from verireview.gh.api import PR_COMMITS_LIMIT
from verireview.gh.models import GhCommit


def build_window(
    thread: ReviewThread,
    pr_commits: Sequence[GhCommit],
    force_pushed_at: Sequence[datetime] = (),
) -> ResolutionWindow:
    """Build the resolution window for ``thread`` from the PR's commits (oldest first)."""
    commits = [to_commit_ref(c) for c in pr_commits]
    comment_at = thread.root.created_at
    start_sha = thread.original_commit_sha
    flags: list[WindowFlag] = []

    if len(pr_commits) >= PR_COMMITS_LIMIT:
        flags.append(WindowFlag.COMMIT_LIST_TRUNCATED)

    index = next((i for i, c in enumerate(commits) if c.sha == start_sha), None)
    if index is not None:
        candidates = commits[index + 1 :]
    else:
        flags.append(WindowFlag.ORIGINAL_COMMIT_NOT_IN_PR)
        if any(t > comment_at for t in force_pushed_at):
            flags.append(WindowFlag.HISTORY_REWRITTEN)
        flags.append(WindowFlag.ORDERED_BY_TIMESTAMP)
        candidates = [c for c in commits if c.committed_at is not None]

    subsequent = [c for c in candidates if c.committed_at is None or c.committed_at >= comment_at]
    excluded = [c for c in candidates if c.committed_at is not None and c.committed_at < comment_at]
    if excluded:
        flags.append(WindowFlag.PRE_COMMENT_COMMITS_EXCLUDED)

    if subsequent:
        end_sha = subsequent[-1].sha
    else:
        end_sha = start_sha
        flags.append(WindowFlag.NO_SUBSEQUENT_COMMITS)

    if thread.is_resolved is None:
        flags.append(WindowFlag.RESOLUTION_STATE_UNKNOWN)
    elif thread.is_resolved:
        flags.append(WindowFlag.RESOLUTION_TIME_UNKNOWN)

    return ResolutionWindow(
        start_commit_sha=start_sha,
        end_commit_sha=end_sha,
        subsequent_commits=subsequent,
        excluded_pre_comment_commits=excluded,
        flags=flags,
    )


def to_commit_ref(commit: GhCommit) -> CommitRef:
    detail = commit.commit
    return CommitRef(
        sha=commit.sha,
        message=detail.message,
        authored_at=detail.author.date if detail.author else None,
        committed_at=detail.committer.date if detail.committer else None,
        author_login=commit.author.login if commit.author else None,
    )
