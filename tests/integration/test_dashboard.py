"""Dashboard pages against PostgreSQL (Phase 13): real audit rows from the worker, hostile
repository content rendered as text, and retention removing stored code."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from helpers.github import C4, FakeGitHubApp, rsa_private_key_pem
from verireview.advisory import GitHubAppAuth
from verireview.advisory.jobs import enqueue, purge_stored_cases
from verireview.advisory.webhooks import AdvisoryTask
from verireview.advisory.worker import AdvisoryWorker
from verireview.config import get_settings
from verireview.dashboard import auth
from verireview.db.models import AdvisoryJob, VerificationAudit
from verireview.db.session import get_sessionmaker
from verireview.main import create_app
from verireview.policy import PolicyConfig

pytestmark = pytest.mark.integration

TOKEN = "dashboard-integration-token"  # noqa: S105 - test value
REPO, INSTALLATION = "acme/shop", 4242
HOSTILE = '<script>alert("x")</script><img src=x onerror=alert(1)>'


def _clean(session: Session) -> None:
    session.execute(delete(VerificationAudit).where(VerificationAudit.repository == REPO))
    session.execute(delete(AdvisoryJob).where(AdvisoryJob.repository == REPO))
    session.commit()


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setenv("VERIREVIEW_DASHBOARD_TOKEN", TOKEN)
    get_settings.cache_clear()
    auth.limiter.reset()
    with get_sessionmaker()() as s:
        _clean(s)
        yield s
        s.rollback()
        _clean(s)
    get_settings.cache_clear()


@pytest.fixture
def client(session: Session) -> TestClient:
    c = TestClient(create_app())
    assert c.post("/dashboard/login", data={"token": TOKEN}).status_code == 200  # followed
    return c


def verified(session: Session) -> VerificationAudit:
    """Run the real worker once on the acme/shop#7 fixture (thread 5001)."""
    task = AdvisoryTask(
        kind="thread",
        installation_id=INSTALLATION,
        repository=REPO,
        pull_number=7,
        comment_id=5001,
        head_sha=C4,
    )
    enqueue(session, f"it-{uuid.uuid4()}", "pull_request_review_thread", [task])
    fake = FakeGitHubApp()
    AdvisoryWorker(
        auth=GitHubAppAuth(1234, SecretStr(rsa_private_key_pem()), transport=fake.transport),
        sessions=get_sessionmaker(),
        policy=PolicyConfig(),
    ).run_once()
    session.expire_all()
    return session.scalars(
        select(VerificationAudit).where(VerificationAudit.repository == REPO)
    ).one()


def test_the_worker_stores_the_verified_case(session: Session) -> None:
    row = verified(session)

    assert row.review_case is not None
    assert row.review_case["file_path"] == "shop/user_service.py"


def test_every_page_shows_the_verification(client: TestClient, session: Session) -> None:
    row = verified(session)

    overview = client.get("/dashboard").text
    assert "acme/shop" in overview and "Eligible categories: <strong>none</strong>" in overview

    repo = client.get(f"/dashboard/r/{INSTALLATION}/acme/shop").text
    assert "#7" in repo and "no opt-in" in repo

    pull = client.get(f"/dashboard/r/{INSTALLATION}/acme/shop/pull/7").text
    assert f"/dashboard/audit/{row.id}" in pull and "comment 5001" in pull

    detail = client.get(f"/dashboard/audit/{row.id}").text
    for expected in (
        "Review thread",  # the thread
        "Requirements",  # per-requirement status with category
        "validation",
        "Evidence",
        "shop/user_service.py:",  # evidence locations
        'class="line marked"',  # highlighted code lines
        'class="add"',  # the diff
        row.inputs_sha256,
    ):
        assert expected in detail, expected

    jobs = client.get("/dashboard/jobs").text
    assert "pull_request_review_thread" in jobs and "done" in jobs


def test_hostile_repository_text_is_rendered_as_text(client: TestClient, session: Session) -> None:
    row = verified(session)
    case = dict(row.review_case or {})
    thread = dict(case["thread"])
    thread["comments"] = [{**thread["comments"][0], "body": HOSTILE, "author": "<b>x</b>"}]
    case["thread"] = thread
    case["after_code"] = f"def f():\n    return '{HOSTILE}'\n"
    case["unified_diff"] = f"+    return '{HOSTILE}'"
    result = dict(row.result)
    result["explanation"] = HOSTILE
    row.review_case, row.result = case, result
    session.commit()

    html = client.get(f"/dashboard/audit/{row.id}").text

    assert "<script>" not in html and "<img" not in html and "<b>x</b>" not in html
    assert "&lt;script&gt;" in html


def test_unknown_or_malformed_addresses_are_not_found(client: TestClient) -> None:
    assert client.get("/dashboard/audit/999999999").status_code == 404
    assert client.get(f"/dashboard/r/{INSTALLATION}/acme/nothing/pull/7").status_code == 404
    assert client.get(f"/dashboard/r/{INSTALLATION}/..%2F..%2Fetc/x").status_code == 404


def test_retention_removes_stored_code_but_keeps_the_verdict(
    client: TestClient, session: Session
) -> None:
    row = verified(session)
    row.created_at = datetime.now(UTC) - timedelta(days=100)
    session.commit()

    assert purge_stored_cases(session, older_than_days=90) == 1
    assert purge_stored_cases(session, older_than_days=90) == 0  # SQL NULL, not JSON null

    session.expire_all()
    kept = session.get(VerificationAudit, row.id)
    assert kept is not None and kept.review_case is None and kept.verdict == row.verdict
    html = client.get(f"/dashboard/audit/{row.id}").text
    assert "stored code for this verification was removed" in html
    assert "Evidence" in html  # the audit trail stays
