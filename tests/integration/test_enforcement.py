"""Phase 12 staged enforcement against PostgreSQL: stages, promotion rules, confirmations, and
when the check may fail (every lock open) or must stay neutral (any lock closed)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from helpers.github import C4, FakeGitHubApp, load_webhook, rsa_private_key_pem
from verireview.advisory import GitHubAppAuth, sign
from verireview.advisory.jobs import enqueue
from verireview.advisory.webhooks import AdvisoryTask
from verireview.advisory.worker import AdvisoryWorker
from verireview.config import get_settings
from verireview.contracts import (
    Confidence,
    RequirementCategory,
    RequirementStatus,
    ReviewCase,
    Verdict,
    VerificationResult,
)
from verireview.db.models import (
    AdvisoryJob,
    RepositoryPolicy,
    RepositoryPolicyChange,
    ReviewConfirmation,
    VerificationAudit,
)
from verireview.db.session import get_sessionmaker
from verireview.enforcement.stages import StageChangeError, change_stage, effective_policy
from verireview.main import create_app
from verireview.policy import OperatingMode, PolicyConfig

pytestmark = pytest.mark.integration

REPO, INSTALLATION = "acme/shop", 4242
SECRET = "integration-webhook-secret"  # noqa: S105 - test value
PEM = rsa_private_key_pem()
NAMING = frozenset({RequirementCategory.NAMING})
M = OperatingMode


def _clean(session: Session) -> None:
    for model in (
        VerificationAudit,
        AdvisoryJob,
        ReviewConfirmation,
        RepositoryPolicyChange,
        RepositoryPolicy,
    ):
        session.execute(delete(model).where(model.repository == REPO))  # type: ignore[attr-defined]
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


def stage(session: Session, to: OperatingMode, **kw: Any) -> RepositoryPolicy:
    kw.setdefault("eligible", frozenset())
    return change_stage(
        session, INSTALLATION, REPO, to, actor="owner", reason="phase 12 integration test", **kw
    )


def confirm(session: Session, n: int) -> None:
    for i in range(n):
        session.add(
            ReviewConfirmation(
                installation_id=INSTALLATION,
                repository=REPO,
                pull_number=7,
                head_sha=uuid.uuid4().hex.rjust(40, "0"),
                reviewer=f"reviewer-{i}",
            )
        )
    session.commit()


def into_enforcement(session: Session) -> None:
    """advisory → human_review (20 days ago) → 10 confirmations → enforcement for naming."""
    stage(session, M.HUMAN_REVIEW, now=datetime.now(UTC) - timedelta(days=20))
    confirm(session, 10)
    stage(session, M.ENFORCEMENT, eligible=NAMING, categories=[RequirementCategory.NAMING])


# ---------------------------------------------------------------- stages


def test_promotion_is_one_step_at_a_time_and_recorded(session: Session) -> None:
    with pytest.raises(StageChangeError, match="one stage at a time"):
        stage(session, M.ENFORCEMENT, eligible=NAMING, categories=[RequirementCategory.NAMING])

    stage(session, M.HUMAN_REVIEW)

    changes = session.scalars(
        select(RepositoryPolicyChange).where(RepositoryPolicyChange.repository == REPO)
    ).all()
    assert [(c.from_stage, c.to_stage, c.actor) for c in changes] == [
        (None, "human_review", "owner")
    ]


def test_enforcement_is_refused_without_eligible_categories(session: Session) -> None:
    stage(session, M.HUMAN_REVIEW, now=datetime.now(UTC) - timedelta(days=30))
    confirm(session, 20)

    with pytest.raises(StageChangeError, match="not eligible.*eligible now: none"):
        stage(session, M.ENFORCEMENT, categories=[RequirementCategory.NAMING])
    with pytest.raises(StageChangeError, match="at least one category"):
        stage(session, M.ENFORCEMENT, eligible=NAMING)


def test_enforcement_needs_time_and_confirmations_in_human_review(session: Session) -> None:
    stage(session, M.HUMAN_REVIEW)
    with pytest.raises(StageChangeError, match="day"):
        stage(session, M.ENFORCEMENT, eligible=NAMING, categories=[RequirementCategory.NAMING])

    stage(session, M.ADVISORY)  # rollback, then human review again, 20 days ago
    stage(session, M.HUMAN_REVIEW, now=datetime.now(UTC) - timedelta(days=20))
    confirm(session, 9)
    with pytest.raises(StageChangeError, match="9 reviewer confirmation"):
        stage(session, M.ENFORCEMENT, eligible=NAMING, categories=[RequirementCategory.NAMING])

    confirm(session, 1)
    row = stage(session, M.ENFORCEMENT, eligible=NAMING, categories=[RequirementCategory.NAMING])
    assert (row.stage, row.enforced_categories) == ("enforcement", ["naming"])


def test_rollback_is_always_allowed(session: Session) -> None:
    into_enforcement(session)

    assert stage(session, M.OBSERVE).stage == "observe"


def test_reason_and_actor_are_required(session: Session) -> None:
    with pytest.raises(StageChangeError, match="reason"):
        change_stage(
            session, INSTALLATION, REPO, M.HUMAN_REVIEW, actor="", reason="x", eligible=frozenset()
        )


def test_repository_without_opt_in_never_enforces(session: Session) -> None:
    default = PolicyConfig(mode=M.ENFORCEMENT, allow_block=True, enforced_categories=NAMING)

    policy = effective_policy(session, INSTALLATION, REPO, default, NAMING)

    assert (policy.mode, policy.allow_block, policy.enforced_categories) == (
        M.HUMAN_REVIEW,
        False,
        frozenset(),
    )


def test_enforced_categories_are_cut_to_current_eligibility(session: Session) -> None:
    into_enforcement(session)
    default = PolicyConfig(mode=M.ENFORCEMENT, allow_block=True)

    assert effective_policy(session, INSTALLATION, REPO, default, NAMING).enforced_categories == (
        NAMING
    )
    # Eligibility withdrawn later (e.g. a new test set): nothing is enforced any more.
    assert effective_policy(
        session, INSTALLATION, REPO, default, frozenset()
    ).enforced_categories == (frozenset())


# ---------------------------------------------------------------- worker and check


class NotSatisfiedNaming:
    """A pipeline double: every thread is a NOT_SATISFIED naming requirement at MEDIUM."""

    def run(self, case: ReviewCase) -> VerificationResult:
        return VerificationResult(
            case_id=case.case_id,
            verdict=Verdict.NOT_SATISFIED,
            confidence=Confidence.MEDIUM,
            per_requirement=[
                RequirementStatus(
                    requirement_id="R1",
                    status=Verdict.NOT_SATISFIED,
                    evidence_ids=[],
                    category=RequirementCategory.NAMING,
                )
            ],
            evidence=[],
            explanation="R1 (naming) not satisfied",
            pipeline_version="test-double",
        )


def worker(
    fake: FakeGitHubApp,
    allow_block: bool = True,
    eligible: frozenset[RequirementCategory] = NAMING,
) -> AdvisoryWorker:
    return AdvisoryWorker(
        auth=GitHubAppAuth(1234, SecretStr(PEM), transport=fake.transport),
        sessions=get_sessionmaker(),
        policy=PolicyConfig(mode=M.ENFORCEMENT, allow_block=allow_block)
        if allow_block
        else PolicyConfig(mode=M.ENFORCEMENT),
        eligible=eligible,
    )


def thread_task() -> AdvisoryTask:
    return AdvisoryTask(
        kind="thread",
        installation_id=INSTALLATION,
        repository=REPO,
        pull_number=7,
        comment_id=5001,
        head_sha=C4,
    )


def conclusion_after_one_job(
    session: Session, monkeypatch: pytest.MonkeyPatch, **worker_kw: Any
) -> str:
    monkeypatch.setattr(
        "verireview.advisory.worker.get_pipeline", lambda _name: NotSatisfiedNaming()
    )
    fake = FakeGitHubApp()
    enqueue(session, f"it-{uuid.uuid4()}", "pull_request_review_thread", [thread_task()])
    assert worker(fake, **worker_kw).run_once()
    [run] = fake.check_runs.values()
    return str(run["conclusion"])


def test_check_fails_only_with_every_lock_open(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    into_enforcement(session)

    assert conclusion_after_one_job(session, monkeypatch) == "failure"
    [audit] = session.scalars(
        select(VerificationAudit).where(VerificationAudit.repository == REPO)
    ).all()
    assert audit.action == "BLOCK"


@pytest.mark.parametrize(
    ("setup", "worker_kw"),
    [
        ("no opt-in", {}),
        ("human review", {}),
        ("enforcement", {"allow_block": False}),
        ("enforcement", {"eligible": frozenset()}),  # the shipped eligibility today
    ],
    ids=["no-opt-in", "human-review-stage", "global-switch-off", "category-not-eligible"],
)
def test_any_closed_lock_keeps_the_check_neutral(
    session: Session, monkeypatch: pytest.MonkeyPatch, setup: str, worker_kw: dict[str, Any]
) -> None:
    if setup == "human review":
        stage(session, M.HUMAN_REVIEW)
    elif setup == "enforcement":
        into_enforcement(session)

    assert conclusion_after_one_job(session, monkeypatch, **worker_kw) == "neutral"


def test_human_review_button_records_the_reviewer_and_updates_the_check(
    session: Session,
) -> None:
    stage(session, M.HUMAN_REVIEW)
    fake = FakeGitHubApp()
    enqueue(session, f"it-{uuid.uuid4()}", "pull_request_review_thread", [thread_task()])
    worker(fake).run_once()
    [run] = fake.check_runs.values()
    assert [a["identifier"] for a in run["actions"]] == ["confirm_review"]

    client = TestClient(create_app())
    body = load_webhook("check_run_rerequested.json").replace(
        b'"action": "rerequested"',
        b'"action": "requested_action", "requested_action": {"identifier": "confirm_review"}',
    )
    response = client.post(
        "/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "check_run",
            "X-GitHub-Delivery": f"it-{uuid.uuid4()}",
            "X-Hub-Signature-256": sign(SECRET, body),
        },
    )
    assert response.json() == {"status": "queued", "jobs": 1}
    worker(fake).run_once()

    reviewers = session.scalars(
        select(ReviewConfirmation.reviewer).where(ReviewConfirmation.repository == REPO)
    ).all()
    assert reviewers == ["dev-alice"]  # the sender of the recorded payload
    [run] = fake.check_runs.values()
    assert "Confirmed by: `dev-alice`" in run["output"]["summary"]
    assert run["conclusion"] == "neutral"
