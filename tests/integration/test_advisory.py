"""Advisory mode end to end, offline: signed webhook → PostgreSQL queue → worker → Check Run.

GitHub is the recorded acme/shop#7 fixture plus a fake App API (tokens, check runs). Needs
PostgreSQL with migrations applied (`alembic upgrade head`).
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from helpers.github import C4, FakeGitHubApp, load_webhook, rsa_private_key_pem
from verireview.advisory import GitHubAppAuth, sign
from verireview.advisory.jobs import enqueue, latest_results
from verireview.advisory.webhooks import AdvisoryTask
from verireview.advisory.worker import AdvisoryWorker
from verireview.config import get_settings
from verireview.db.models import AdvisoryJob, VerificationAudit
from verireview.db.session import get_sessionmaker
from verireview.main import create_app
from verireview.policy import OperatingMode, PolicyConfig

pytestmark = pytest.mark.integration

SECRET = "integration-webhook-secret"  # noqa: S105 - test value
PEM = rsa_private_key_pem()


def _clean(session: Session) -> None:
    session.execute(delete(VerificationAudit).where(VerificationAudit.repository == "acme/shop"))
    session.execute(delete(AdvisoryJob).where(AdvisoryJob.repository == "acme/shop"))
    session.commit()


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setenv("VERIREVIEW_GITHUB_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    with get_sessionmaker()() as s:
        _clean(s)
        yield s
        s.rollback()
        _clean(s)
    get_settings.cache_clear()


@pytest.fixture
def client(session: Session) -> TestClient:
    return TestClient(create_app())


def worker(fake: FakeGitHubApp, mode: OperatingMode = OperatingMode.ADVISORY) -> AdvisoryWorker:
    return AdvisoryWorker(
        auth=GitHubAppAuth(1234, SecretStr(PEM), transport=fake.transport),
        sessions=get_sessionmaker(),
        policy=PolicyConfig(mode=mode),
    )


def deliver(client: TestClient, name: str, event: str, delivery: str, signed: bool = True) -> int:
    body = load_webhook(name)
    headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": delivery}
    if signed:
        headers["X-Hub-Signature-256"] = sign(SECRET, body)
    return client.post("/github/webhook", content=body, headers=headers).status_code


def jobs(session: Session, delivery: str) -> list[AdvisoryJob]:
    session.expire_all()
    return list(session.scalars(select(AdvisoryJob).where(AdvisoryJob.delivery_id == delivery)))


def audits(session: Session) -> list[VerificationAudit]:
    session.expire_all()
    return list(
        session.scalars(
            select(VerificationAudit).where(VerificationAudit.repository == "acme/shop")
        )
    )


def test_resolved_thread_ends_as_one_neutral_check_with_an_audit_row(
    client: TestClient, session: Session
) -> None:
    delivery = f"it-{uuid.uuid4()}"
    fake = FakeGitHubApp()

    assert deliver(client, "thread_resolved.json", "pull_request_review_thread", delivery) == 202
    assert worker(fake).run_once() is True

    [job] = jobs(session, delivery)
    assert (job.status, job.attempts) == ("done", 1)
    [audit] = audits(session)
    assert (audit.comment_id, audit.head_sha, audit.pipeline_version) == (5001, C4, "mvp-2")
    assert len(audit.inputs_sha256) == 64 and audit.result["verdict"] == audit.verdict

    [run] = fake.check_runs.values()
    assert (run["name"], run["head_sha"], run["conclusion"]) == ("VeriReview", C4, "neutral")
    # The injected text in the webhook body is never used: the comment is re-read from GitHub.
    assert "Ignore previous instructions" not in str(run["output"])
    assert "evil.example" not in str(run["output"])
    # Every repository call used the scoped installation token, not the App JWT.
    repo_calls = [r for r in fake.requests if r.url.path.startswith("/repos/")]
    assert repo_calls
    assert all(r.headers["authorization"] == f"Bearer {FakeGitHubApp.TOKEN}" for r in repo_calls)


def test_duplicate_delivery_is_processed_once(client: TestClient, session: Session) -> None:
    delivery = f"it-{uuid.uuid4()}"
    fake = FakeGitHubApp()

    assert deliver(client, "thread_resolved.json", "pull_request_review_thread", delivery) == 202
    assert deliver(client, "thread_resolved.json", "pull_request_review_thread", delivery) == 202

    assert len(jobs(session, delivery)) == 1
    assert worker(fake).run_once() is True
    assert worker(fake).run_once() is False
    assert len(audits(session)) == 1


def test_forged_webhook_is_rejected_and_queues_nothing(
    client: TestClient, session: Session
) -> None:
    delivery = f"it-{uuid.uuid4()}"

    assert (
        deliver(client, "thread_resolved.json", "pull_request_review_thread", delivery, False)
        == 401
    )
    assert jobs(session, delivery) == []


def test_rerun_reverifies_resolved_threads_and_updates_the_same_check(
    client: TestClient, session: Session
) -> None:
    fake = FakeGitHubApp()
    deliver(client, "thread_resolved.json", "pull_request_review_thread", f"it-{uuid.uuid4()}")
    worker(fake).run_once()
    deliver(client, "check_run_rerequested.json", "check_run", f"it-{uuid.uuid4()}")
    worker(fake).run_once()

    assert len(fake.check_runs) == 1  # updated, not duplicated
    assert [r.method for r in fake.requests if r.url.path.endswith("/check-runs/1")] == ["PATCH"]
    assert sorted(a.comment_id for a in audits(session)) == [5001, 5001]  # 5003 is unresolved


def test_observe_mode_audits_but_posts_nothing(session: Session) -> None:
    fake = FakeGitHubApp()
    enqueue(session, f"it-{uuid.uuid4()}", "pull_request_review_thread", [task()])

    worker(fake, OperatingMode.OBSERVE).run_once()

    assert len(audits(session)) == 1
    assert fake.check_runs == {}


def task(comment_id: int = 5001) -> AdvisoryTask:
    return AdvisoryTask(
        kind="thread",
        installation_id=4242,
        repository="acme/shop",
        pull_number=7,
        comment_id=comment_id,
        head_sha=C4,
    )


def test_github_outage_is_retried_later_without_leaking_the_token(session: Session) -> None:
    delivery = f"it-{uuid.uuid4()}"
    enqueue(session, delivery, "pull_request_review_thread", [task()])

    worker(FakeGitHubApp(fail_path="/repos/acme/shop/pulls/7")).run_once()

    [job] = jobs(session, delivery)
    assert (job.status, job.attempts) == ("queued", 1)
    assert job.last_error is not None and "GitHubRequestError" in job.last_error
    assert FakeGitHubApp.TOKEN not in job.last_error
    assert job.available_at > job.created_at  # backed off


def test_unknown_thread_fails_permanently(session: Session) -> None:
    delivery = f"it-{uuid.uuid4()}"
    enqueue(session, delivery, "pull_request_review_thread", [task(comment_id=999_999)])

    worker(FakeGitHubApp()).run_once()

    [job] = jobs(session, delivery)
    assert job.status == "failed"
    assert audits(session) == []


def test_audit_results_are_isolated_by_installation_and_repository(session: Session) -> None:
    enqueue(session, f"it-{uuid.uuid4()}", "pull_request_review_thread", [task()])
    worker(FakeGitHubApp()).run_once()

    assert len(latest_results(session, 4242, "acme/shop", 7, C4)) == 1
    assert latest_results(session, 9999, "acme/shop", 7, C4) == []
    assert latest_results(session, 4242, "acme/other", 7, C4) == []


def test_check_stays_neutral_even_if_blocking_were_configured(session: Session) -> None:
    fake = FakeGitHubApp()
    enqueue(session, f"it-{uuid.uuid4()}", "pull_request_review_thread", [task()])
    blocking = AdvisoryWorker(
        auth=GitHubAppAuth(1234, SecretStr(PEM), transport=fake.transport),
        sessions=get_sessionmaker(),
        policy=PolicyConfig(mode=OperatingMode.ENFORCEMENT, allow_block=True),
    )

    blocking.run_once()

    assert [run["conclusion"] for run in fake.check_runs.values()] == ["neutral"]
