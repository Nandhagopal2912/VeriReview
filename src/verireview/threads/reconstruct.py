"""Group flat PR review comments into threads and attach resolution state.

GitHub REST returns review comments as a flat list. A reply's ``in_reply_to_id`` points at the
thread's root comment, but chains are followed defensively in case a reply points at a reply.
"""

from collections.abc import Iterable

from verireview.contracts import ReviewThread, ThreadComment
from verireview.gh.models import GhReviewComment, GhThreadState


class ThreadNotFoundError(LookupError):
    pass


def reconstruct_threads(
    comments: Iterable[GhReviewComment],
    states: Iterable[GhThreadState] | None = None,
) -> list[ReviewThread]:
    """Return one ReviewThread per root comment, ordered by root creation time.

    ``states`` (from GraphQL) sets ``is_resolved``; when None, resolution is unknown.
    """
    by_id = {c.id: c for c in comments}
    members: dict[int, list[GhReviewComment]] = {}
    for comment in by_id.values():
        members.setdefault(_root_id(comment, by_id), []).append(comment)

    state_by_root = {s.root_comment_id: s for s in states} if states is not None else None

    threads: list[ReviewThread] = []
    for root_id, group in members.items():
        root = by_id.get(root_id)
        if root is None:
            # Root comment was deleted; the thread cannot be anchored to code.
            continue
        group.sort(key=lambda c: (c.created_at, c.id))
        state = state_by_root.get(root_id) if state_by_root is not None else None
        threads.append(
            ReviewThread(
                root_comment_id=root.id,
                path=root.path,
                line=root.line,
                original_line=root.original_line,
                start_line=root.start_line,
                original_start_line=root.original_start_line,
                side=root.side,
                diff_hunk=root.diff_hunk,
                original_commit_sha=root.original_commit_id,
                commit_sha=root.commit_id,
                comments=[_to_thread_comment(c) for c in group],
                is_resolved=state.is_resolved if state else None,
                resolved_by=state.resolved_by if state else None,
                is_outdated=state.is_outdated if state else None,
            )
        )
    threads.sort(key=lambda t: (t.root.created_at, t.root_comment_id))
    return threads


def find_thread(threads: Iterable[ReviewThread], comment_id: int) -> ReviewThread:
    """Find the thread containing ``comment_id`` (root or reply)."""
    for thread in threads:
        if any(c.id == comment_id for c in thread.comments):
            return thread
    raise ThreadNotFoundError(f"No review thread contains comment {comment_id}")


def _root_id(comment: GhReviewComment, by_id: dict[int, GhReviewComment]) -> int:
    current = comment
    seen = {current.id}
    while current.in_reply_to_id is not None:
        parent = by_id.get(current.in_reply_to_id)
        if parent is None:
            return current.in_reply_to_id
        if parent.id in seen:  # cycle guard for malformed data
            break
        seen.add(parent.id)
        current = parent
    return current.id


def _to_thread_comment(comment: GhReviewComment) -> ThreadComment:
    return ThreadComment(
        id=comment.id,
        author=comment.user.login if comment.user else None,
        body=comment.body,
        created_at=comment.created_at,
        in_reply_to_id=comment.in_reply_to_id,
    )
