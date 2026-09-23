"""MVP end to end: GitHub → ReviewCase → PostgreSQL → reload → verify → policy.

Needs PostgreSQL with migrations applied (`alembic upgrade head`). GitHub is the recorded fixture.
"""

import uuid
from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.orm import Session

from helpers.github import FakeGitHub
from verireview.contracts import ReviewCase, Verdict
from verireview.db.models import Repository
from verireview.db.session import get_sessionmaker
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.ingestion import ingest_review_case
from verireview.ingestion.store import load_review_case, save_review_case
from verireview.policy import Action, decide
from verireview.verification import mvp_pipeline

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    with get_sessionmaker()() as s:
        yield s
        s.rollback()
        s.execute(delete(Repository).where(Repository.full_name.like("e2e-%")))
        s.commit()


def ingested() -> ReviewCase:
    client = GitHubClient(SecretStr("t"), transport=FakeGitHub().transport)
    case = ingest_review_case(GitHubApi(client), RepoRef("acme/shop"), 7, 5001)
    repo = f"e2e-{uuid.uuid4().hex[:10]}/shop"
    return case.model_copy(
        update={"repository": repo, "case_id": ReviewCase.make_case_id(repo, 7, 5001)}
    )


def test_case_survives_storage_and_verifies_identically(session: Session) -> None:
    case = ingested()
    direct = mvp_pipeline().run(case)

    save_review_case(session, case)
    reloaded = load_review_case(session, case.case_id)

    assert reloaded == case  # ReviewCase flows through storage unchanged
    assert mvp_pipeline().run(reloaded) == direct


def test_full_flow_reaches_a_policy_decision(session: Session) -> None:
    case = ingested()
    save_review_case(session, case)
    reloaded = load_review_case(session, case.case_id)
    assert reloaded is not None

    result = mvp_pipeline().run(reloaded)
    decision = decide(result)

    assert result.verdict == Verdict.SATISFIED
    assert [s.status for s in result.per_requirement] == [Verdict.SATISFIED, Verdict.SATISFIED]
    assert decision.action == Action.ALLOW
    assert not decision.blocks_merge
