"""Persist a ReviewCase. Re-ingesting the same case updates it in place (idempotent)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from verireview.contracts import ReviewCase
from verireview.db.models import (
    CommitRow,
    PullRequest,
    Repository,
    ReviewCaseRow,
    ReviewCommentRow,
    ReviewThreadRow,
)


def save_review_case(session: Session, case: ReviewCase) -> int:
    """Upsert the case and its repository, PR, thread, comments and commits. Returns the row id."""
    repository_id = _upsert(
        session, Repository, {"full_name": case.repository}, ["full_name"], update=False
    )
    pull_id = _upsert(
        session,
        PullRequest,
        {
            "repository_id": repository_id,
            "number": case.pull_number,
            "title": case.pull_title,
            "base_sha": case.base_sha,
            "head_sha": case.head_sha,
            "fetched_at": case.ingested_at,
        },
        ["repository_id", "number"],
    )
    thread = case.thread
    thread_id = _upsert(
        session,
        ReviewThreadRow,
        {
            "pull_request_id": pull_id,
            "root_comment_id": thread.root_comment_id,
            "path": thread.path,
            "original_line": thread.original_line,
            "original_commit_sha": thread.original_commit_sha,
            "is_resolved": thread.is_resolved,
            "is_outdated": thread.is_outdated,
            "resolved_by": thread.resolved_by,
        },
        ["pull_request_id", "root_comment_id"],
    )
    for comment in thread.comments:
        _upsert(
            session,
            ReviewCommentRow,
            {
                "thread_id": thread_id,
                "github_id": comment.id,
                "in_reply_to_id": comment.in_reply_to_id,
                "author": comment.author,
                "body": comment.body,
                "created_at": comment.created_at,
            },
            ["thread_id", "github_id"],
        )
    window = case.window
    for commit in [
        *window.excluded_pre_comment_commits,
        *window.ambiguous_rewritten_commits,
        *window.subsequent_commits,
    ]:
        _upsert(
            session,
            CommitRow,
            {"repository_id": repository_id, **commit.model_dump()},
            ["repository_id", "sha"],
            update=False,
        )
    case_row_id = _upsert(
        session,
        ReviewCaseRow,
        {
            "repository_id": repository_id,
            "pull_request_id": pull_id,
            "case_id": case.case_id,
            "schema_version": case.schema_version,
            "payload": case.model_dump(mode="json"),
            "ingested_at": case.ingested_at,
        },
        ["case_id"],
    )
    session.commit()
    return case_row_id


def load_review_case(session: Session, case_id: str) -> ReviewCase | None:
    payload = session.scalar(select(ReviewCaseRow.payload).where(ReviewCaseRow.case_id == case_id))
    return None if payload is None else ReviewCase.model_validate(payload)


def _upsert(
    session: Session,
    model: type[Any],
    values: dict[str, Any],
    conflict_columns: list[str],
    update: bool = True,
) -> int:
    """INSERT ... ON CONFLICT and return the row id (existing or new)."""
    stmt = insert(model).values(**values)
    changes = {k: v for k, v in values.items() if k not in conflict_columns}
    if update and changes:
        stmt = stmt.on_conflict_do_update(index_elements=conflict_columns, set_=changes)
    else:
        # A no-op update so RETURNING yields the existing row's id.
        first = conflict_columns[0]
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns, set_={first: getattr(stmt.excluded, first)}
        )
    row_id: int = session.execute(stmt.returning(model.id)).scalar_one()
    return row_id
