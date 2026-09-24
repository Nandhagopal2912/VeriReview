"""Demo data (``verireview demo-seed``): real fixture verifications under installation 0 that
every dashboard page can show, replaced on re-seed and removed without touching real rows."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verireview.advisory import demo
from verireview.config import get_settings
from verireview.dashboard import auth
from verireview.db.models import (
    AdvisoryJob,
    RepositoryPolicy,
    RepositoryPolicyChange,
    ReviewConfirmation,
    VerificationAudit,
)
from verireview.db.session import get_sessionmaker
from verireview.main import create_app

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[2] / "dataset" / "fixtures"
TOKEN = "demo-integration-token"  # noqa: S105 - test value


def _demo_audits(session: Session) -> int:
    return (
        session.scalar(
            select(func.count(VerificationAudit.id)).where(
                VerificationAudit.installation_id == demo.DEMO_INSTALLATION
            )
        )
        or 0
    )


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setenv("VERIREVIEW_DASHBOARD_TOKEN", TOKEN)
    get_settings.cache_clear()
    auth.limiter.reset()
    with get_sessionmaker()() as s:
        had_demo = _demo_audits(s) > 0  # the operator's own demo data survives the test
        yield s
        s.rollback()
        if had_demo:
            demo.seed(s, FIXTURES)
        else:
            demo.remove(s)
    get_settings.cache_clear()


def test_seed_verifies_every_fixture_and_shows_on_every_page(session: Session) -> None:
    summary = demo.seed(session, FIXTURES)
    fixtures = len(list(FIXTURES.glob("*/meta.json")))
    assert summary.verifications == fixtures + 1  # one thread is verified twice
    assert set(summary.verdicts) == {
        "SATISFIED",
        "PARTIALLY_SATISFIED",
        "NOT_SATISFIED",
        "UNCERTAIN",
    }
    assert _demo_audits(session) == summary.verifications

    policy = session.scalars(
        select(RepositoryPolicy).where(RepositoryPolicy.installation_id == demo.DEMO_INSTALLATION)
    ).one()
    assert (policy.repository, policy.stage) == (demo.PROMOTED, "human_review")
    changes = session.scalars(
        select(RepositoryPolicyChange.to_stage)
        .where(RepositoryPolicyChange.installation_id == demo.DEMO_INSTALLATION)
        .order_by(RepositoryPolicyChange.id)
    ).all()
    assert changes == ["observe", "advisory", "human_review"]
    confirmed = select(func.count(ReviewConfirmation.id)).where(
        ReviewConfirmation.installation_id == demo.DEMO_INSTALLATION
    )
    assert session.scalar(confirmed) == 2
    demo_jobs = select(AdvisoryJob.status).where(
        AdvisoryJob.installation_id == demo.DEMO_INSTALLATION
    )
    statuses = session.scalars(demo_jobs).all()
    assert "queued" not in statuses and "failed" in statuses  # a worker never picks demo work up

    # The thread verified twice: unchanged first (not satisfied), then fixed.
    rows = session.scalars(
        select(VerificationAudit)
        .where(VerificationAudit.installation_id == demo.DEMO_INSTALLATION)
        .order_by(VerificationAudit.id)
    ).all()
    by_thread: dict[int, list[VerificationAudit]] = {}
    for row in rows:
        by_thread.setdefault(row.comment_id, []).append(row)
    twice = [r for r in by_thread.values() if len(r) == 2]
    assert len(twice) == 1
    assert [r.verdict for r in twice[0]] == ["NOT_SATISFIED", "SATISFIED"]

    client = TestClient(create_app())
    assert client.post("/dashboard/login", data={"token": TOKEN}).status_code == 200
    overview = client.get("/dashboard").text
    assert "demo/shop-api" in overview and "(demo)" in overview
    first = twice[0][1]
    base = f"/dashboard/r/0/{first.repository}"
    assert "human_review" in client.get(base).text
    assert client.get(f"{base}/pull/{first.pull_number}").status_code == 200
    detail = client.get(f"/dashboard/audit/{first.id}").text
    assert "SATISFIED" in detail and first.inputs_sha256 in detail
    assert "simulated" in client.get("/dashboard/jobs").text


def test_reseed_replaces_and_remove_touches_only_demo_rows(session: Session) -> None:
    real = VerificationAudit(
        installation_id=77,
        repository="acme/real",
        pull_number=1,
        comment_id=1,
        head_sha="a" * 40,
        inputs_sha256="b" * 64,
        pipeline_version="mvp-2",
        verdict="SATISFIED",
        confidence="MEDIUM",
        action="ALLOW",
        result={},
    )
    session.add(real)
    session.commit()
    try:
        first = demo.seed(session, FIXTURES)
        assert demo.seed(session, FIXTURES) == first  # replaced, not doubled
        assert _demo_audits(session) == first.verifications
        assert demo.remove(session) == first.verifications
        assert _demo_audits(session) == 0
        assert session.get(VerificationAudit, real.id) is not None
    finally:
        session.delete(real)
        session.commit()
