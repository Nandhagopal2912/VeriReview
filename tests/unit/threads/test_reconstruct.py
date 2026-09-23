import pytest

from helpers.github import gh_comment
from verireview.gh.models import GhThreadState
from verireview.threads import ThreadNotFoundError, find_thread, reconstruct_threads

COMMENTS = [
    gh_comment(10, "2026-01-01T12:00:00Z", body="Please validate username."),
    gh_comment(12, "2026-01-01T12:30:00Z", in_reply_to_id=10, author="dev-alice"),
    gh_comment(20, "2026-01-01T11:00:00Z", body="nit"),
    gh_comment(11, "2026-01-01T12:10:00Z", in_reply_to_id=10, author="rev-carol"),
]


def test_groups_replies_under_root_in_chronological_order() -> None:
    threads = reconstruct_threads(COMMENTS)

    assert [t.root_comment_id for t in threads] == [20, 10]  # ordered by root creation
    thread = threads[1]
    assert [c.id for c in thread.comments] == [10, 11, 12]
    assert thread.root.body == "Please validate username."


def test_resolution_unknown_without_states() -> None:
    threads = reconstruct_threads(COMMENTS)

    assert all(t.is_resolved is None and t.resolved_by is None for t in threads)


def test_attaches_resolution_state_by_root_comment() -> None:
    states = [
        GhThreadState(root_comment_id=10, is_resolved=True, is_outdated=False, resolved_by="x")
    ]

    threads = {t.root_comment_id: t for t in reconstruct_threads(COMMENTS, states)}

    assert threads[10].is_resolved is True
    assert threads[10].resolved_by == "x"
    # States were available but this thread had none: still unknown, never guessed.
    assert threads[20].is_resolved is None


def test_reply_to_reply_is_attached_to_root() -> None:
    comments = [
        gh_comment(1, "2026-01-01T10:00:00Z"),
        gh_comment(2, "2026-01-01T10:01:00Z", in_reply_to_id=1),
        gh_comment(3, "2026-01-01T10:02:00Z", in_reply_to_id=2),
    ]

    (thread,) = reconstruct_threads(comments)

    assert [c.id for c in thread.comments] == [1, 2, 3]


def test_thread_with_deleted_root_is_dropped() -> None:
    orphan = [gh_comment(2, "2026-01-01T10:01:00Z", in_reply_to_id=999)]

    assert reconstruct_threads(orphan) == []


def test_cycle_in_reply_chain_does_not_hang() -> None:
    comments = [
        gh_comment(1, "2026-01-01T10:00:00Z", in_reply_to_id=2),
        gh_comment(2, "2026-01-01T10:01:00Z", in_reply_to_id=1),
    ]

    reconstruct_threads(comments)  # must terminate


def test_find_thread_by_reply_id() -> None:
    threads = reconstruct_threads(COMMENTS)

    assert find_thread(threads, 12).root_comment_id == 10


def test_find_thread_unknown_comment() -> None:
    with pytest.raises(ThreadNotFoundError):
        find_thread(reconstruct_threads(COMMENTS), 404)
