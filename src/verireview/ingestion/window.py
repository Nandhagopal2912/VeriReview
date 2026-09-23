"""Temporal review-resolution window (plan §6).

Which commits could be a response to the review comment?

1. Locate the reviewed commit (``original_commit_sha``) in the PR's ordered commit list.
   Every later commit is a candidate.
2. Candidates committed *before* the comment was written cannot be responses to it (the
   reviewer was looking at an older commit), so they are excluded and reported separately.
3. If the reviewed commit is not in the list (force-push/rebase, or the 250-commit API cap),
   fall back to timestamps and flag the window as less reliable. A rebase resets *committer*
   dates but keeps *author* dates, while ``git commit --amend`` keeps the author date too.
   So (live check on pallets/click#2622 and #3460):

   - authored at/after the comment            → response candidate
   - committed before the comment             → pre-comment, excluded
   - authored before, committed after comment → ambiguous (rebased old work *or* an amended
     response); reported separately, never guessed

4. The window ends at the last candidate or ambiguous commit. GitHub exposes whether a thread
   is resolved but not *when*, flagged ``RESOLUTION_TIME_UNKNOWN``. Webhook events (Phase 11)
   will give the exact time.

This module is pure: no I/O, fully deterministic.
"""

from collections.abc import Sequence
from datetime import datetime

from verireview.contracts import CommitRef, ResolutionWindow, ReviewThread, WindowFlag
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

    ambiguous: list[CommitRef] = []
    index = next((i for i, c in enumerate(commits) if c.sha == start_sha), None)
    if index is not None:
        candidates = commits[index + 1 :]
        subsequent = [c for c in candidates if not _before(c.committed_at, comment_at)]
        excluded = [c for c in candidates if _before(c.committed_at, comment_at)]
    else:
        flags.append(WindowFlag.ORIGINAL_COMMIT_NOT_IN_PR)
        if any(t > comment_at for t in force_pushed_at):
            flags.append(WindowFlag.HISTORY_REWRITTEN)
        flags.append(WindowFlag.ORDERED_BY_TIMESTAMP)
        excluded = [c for c in commits if _before(c.committed_at, comment_at)]
        later = [c for c in commits if not _before(c.committed_at, comment_at)]
        subsequent = [c for c in later if not _before(c.authored_at, comment_at)]
        ambiguous = [c for c in later if _before(c.authored_at, comment_at)]
        if ambiguous:
            flags.append(WindowFlag.AMBIGUOUS_REWRITTEN_COMMITS)

    if excluded:
        flags.append(WindowFlag.PRE_COMMENT_COMMITS_EXCLUDED)

    in_window = {c.sha for c in (*subsequent, *ambiguous)}
    last = next((c for c in reversed(commits) if c.sha in in_window), None)
    if not subsequent:
        flags.append(WindowFlag.NO_SUBSEQUENT_COMMITS)
    end_sha = last.sha if last is not None else start_sha

    if thread.is_resolved is None:
        flags.append(WindowFlag.RESOLUTION_STATE_UNKNOWN)
    elif thread.is_resolved:
        flags.append(WindowFlag.RESOLUTION_TIME_UNKNOWN)

    return ResolutionWindow(
        start_commit_sha=start_sha,
        end_commit_sha=end_sha,
        subsequent_commits=subsequent,
        ambiguous_rewritten_commits=ambiguous,
        excluded_pre_comment_commits=excluded,
        flags=flags,
    )


def _before(moment: datetime | None, comment_at: datetime) -> bool:
    """Strictly before the comment. Unknown dates are never treated as 'before'."""
    return moment is not None and moment < comment_at


def to_commit_ref(commit: GhCommit) -> CommitRef:
    detail = commit.commit
    return CommitRef(
        sha=commit.sha,
        message=detail.message,
        authored_at=detail.author.date if detail.author else None,
        committed_at=detail.committer.date if detail.committer else None,
        author_login=commit.author.login if commit.author else None,
    )
