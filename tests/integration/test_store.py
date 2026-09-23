"""ReviewCase persistence against real PostgreSQL. Needs: alembic upgrade head."""

import uuid
from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from helpers.github import FakeGitHub
from verireview.contracts import ReviewCase
from verireview.db.models import (
    CommitRow,
    PullRequest,
    Repository,
    ReviewCaseRow,
    ReviewCommentRow,
    ReviewThreadRow,
)
from verireview.db.session import get_sessionmaker
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.ingestion import ingest_review_case
from verireview.ingestion.store import load_review_case, save_review_case

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def case(session: Session) -> Iterator[ReviewCase]:
    """The fixture case under a unique repository name, deleted afterwards."""
    client = GitHubClient(SecretStr("t"), transport=FakeGitHub().transport)
    base = ingest_review_case(GitHubApi(client), RepoRef("acme/shop"), 7, 5001)
    repo = f"test-{uuid.uuid4().hex[:12]}/shop"
    yield base.model_copy(
        update={"repository": repo, "case_id": ReviewCase.make_case_id(repo, 7, 5001)}
    )
    session.rollback()
    session.execute(delete(Repository).where(Repository.full_name.like("test-%")))
    session.commit()


def test_save_and_load_round_trip(session: Session, case: ReviewCase) -> None:
    save_review_case(session, case)

    assert load_review_case(session, case.case_id) == case


def test_saving_twice_is_idempotent(session: Session, case: ReviewCase) -> None:
    first = save_review_case(session, case)
    second = save_review_case(session, case.model_copy(update={"pull_title": "Renamed"}))

    assert first == second
    stored = load_review_case(session, case.case_id)
    assert stored is not None and stored.pull_title == "Renamed"
    comments = session.scalar(
        select(func.count())
        .select_from(ReviewCommentRow)
        .join(ReviewThreadRow, ReviewThreadRow.id == ReviewCommentRow.thread_id)
        .join(PullRequest, PullRequest.id == ReviewThreadRow.pull_request_id)
        .join(Repository, Repository.id == PullRequest.repository_id)
        .where(Repository.full_name == case.repository)
    )
    assert comments == len(case.thread.comments)


def test_same_pr_number_in_two_repositories_is_isolated(session: Session, case: ReviewCase) -> None:
    other_repo = f"test-{uuid.uuid4().hex[:12]}/shop"
    other = case.model_copy(
        update={"repository": other_repo, "case_id": ReviewCase.make_case_id(other_repo, 7, 5001)}
    )

    save_review_case(session, case)
    save_review_case(session, other)

    repo_ids = session.scalars(
        select(ReviewCaseRow.repository_id).where(
            ReviewCaseRow.case_id.in_([case.case_id, other.case_id])
        )
    ).all()
    assert len(set(repo_ids)) == 2
    commit_counts = session.execute(
        select(CommitRow.repository_id, func.count())
        .where(CommitRow.repository_id.in_(repo_ids))
        .group_by(CommitRow.repository_id)
    ).all()
    assert sorted(count for _, count in commit_counts) == [2, 2]


def test_load_unknown_case_returns_none(session: Session) -> None:
    assert load_review_case(session, "nope/nope#1/1") is None
