"""Demo data for the dashboard: real verifications of the built-in dev fixtures.

``verireview demo-seed`` runs the default pipeline on every fixture in ``dataset/fixtures`` and
stores the results the way the advisory worker would (a finished job, an audit row with the
verified ReviewCase), under **installation 0** and fictional ``demo/…`` repositories. Nothing
here talks to GitHub. It also records a stage history (observe → advisory → human_review, through
the normal rollout rules), two reviewer confirmations, one failed job, and one thread verified
twice (first with no changes, then fixed) so every dashboard page has something to show.

GitHub never issues installation id 0, so demo rows cannot mix with real ones, and
``remove`` deletes exactly them. Seeding replaces earlier demo rows. No job is left queued, so a
running worker never picks demo work up.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from verireview.advisory.jobs import DONE, FAILED, record_audit
from verireview.contracts import ResolutionWindow, ReviewCase, WindowFlag
from verireview.dataset import Fixture, iter_fixtures
from verireview.db.models import (
    AdvisoryJob,
    RepositoryPolicy,
    RepositoryPolicyChange,
    ReviewConfirmation,
    VerificationAudit,
)
from verireview.enforcement.stages import change_stage, effective_policy
from verireview.policy import OperatingMode, PolicyConfig, decide
from verireview.verification import get_pipeline

DEMO_INSTALLATION = 0
ACTOR = "demo-seed"
EVENT = "pull_request_review_thread"

# Fixture-name prefix -> fictional repository. Each repository gets pull requests of up to
# PER_PULL fixtures, numbered from 101.
REPOSITORIES = {
    "api-": "demo/shop-api",
    "validation-": "demo/shop-api",
    "errors-": "demo/payments",
    "naming-": "demo/accounts",
    "testing-": "demo/accounts",
}
PER_PULL = 3
PROMOTED = "demo/shop-api"  # walked observe -> advisory -> human_review
EARLIER_ATTEMPT = "validation-001-none-check"  # verified twice: unchanged first, then fixed
FAILED_REPOSITORY = "demo/payments"


@dataclass(frozen=True)
class DemoSummary:
    repositories: int
    pull_requests: int
    verifications: int
    verdicts: dict[str, int]


def remove(session: Session) -> int:
    """Delete every demo row (installation 0); returns how many audit rows went."""
    audits = session.scalar(
        select(func.count(VerificationAudit.id)).where(
            VerificationAudit.installation_id == DEMO_INSTALLATION
        )
    )
    session.execute(
        delete(VerificationAudit).where(VerificationAudit.installation_id == DEMO_INSTALLATION)
    )
    for model in (AdvisoryJob, ReviewConfirmation, RepositoryPolicyChange, RepositoryPolicy):
        session.execute(delete(model).where(model.installation_id == DEMO_INSTALLATION))
    session.commit()
    return int(audits or 0)


def seed(session: Session, fixtures_root: Path, now: datetime | None = None) -> DemoSummary:
    """Replace the demo rows with fresh verifications of every fixture under ``fixtures_root``."""
    now = now or datetime.now(UTC)
    fixtures = list(iter_fixtures(fixtures_root))
    if not fixtures:
        raise ValueError(f"no fixtures under {fixtures_root}")
    remove(session)

    pipeline = get_pipeline()
    groups = _pull_requests(fixtures)
    step = timedelta(hours=5)
    at = now - step * (len(fixtures) + 2)
    _promote(session, at)
    verdicts: dict[str, int] = {}
    count = 0
    for (repository, number), members in groups.items():
        job = _job(session, repository, number, DONE, at)
        policy = effective_policy(
            session, DEMO_INSTALLATION, repository, PolicyConfig(), frozenset()
        )
        for fixture in members:
            attempts = [_unchanged(fixture.case)] if fixture.meta.case_id == EARLIER_ATTEMPT else []
            for case in [*attempts, fixture.case]:
                case = case.model_copy(update={"repository": repository, "pull_number": number})
                result = pipeline.run(case)
                row = record_audit(
                    session, job, case, case.thread.root_comment_id, result, decide(result, policy)
                )
                row.created_at = at
                at += step
                verdicts[row.verdict] = verdicts.get(row.verdict, 0) + 1
                count += 1
            if repository == PROMOTED and len(_reviewers(session)) < 2:
                _confirm(session, repository, number, fixture.case.head_sha, at)
        job.updated_at = at
    failed = _job(session, FAILED_REPOSITORY, 999, FAILED, at)
    failed.last_error = (
        "demo: GitHub API 503 Service Unavailable (simulated), gave up after 5 attempts"
    )
    failed.attempts = 5
    session.commit()
    return DemoSummary(
        repositories=len({repo for repo, _ in groups}),
        pull_requests=len(groups),
        verifications=count,
        verdicts=verdicts,
    )


def _promote(session: Session, first_verification: datetime) -> None:
    """Walk the promoted repository up to human_review with the normal rules, a day apart."""
    stages = [
        (OperatingMode.OBSERVE, "demo data: opt in, observe only"),
        (OperatingMode.ADVISORY, "demo data: show the neutral check"),
        (OperatingMode.HUMAN_REVIEW, "demo data: reviewers confirm results"),
    ]
    for days_before, (stage, reason) in zip((3, 2, 1), stages, strict=True):
        at = first_verification - timedelta(days=days_before)
        change_stage(
            session, DEMO_INSTALLATION, PROMOTED, stage,
            actor=ACTOR, reason=reason, eligible=frozenset(), now=at,
        )  # fmt: skip
        change = session.scalars(
            select(RepositoryPolicyChange)
            .where(RepositoryPolicyChange.installation_id == DEMO_INSTALLATION)
            .order_by(RepositoryPolicyChange.id.desc())
        ).first()
        if change is not None:
            change.created_at = at
    session.commit()


def _pull_requests(fixtures: list[Fixture]) -> dict[tuple[str, int], list[Fixture]]:
    by_repository: dict[str, list[Fixture]] = {}
    for fixture in fixtures:
        repository = next(
            (r for prefix, r in REPOSITORIES.items() if fixture.meta.case_id.startswith(prefix)),
            "demo/misc",
        )
        by_repository.setdefault(repository, []).append(fixture)
    groups: dict[tuple[str, int], list[Fixture]] = {}
    for repository, members in by_repository.items():
        for index in range(0, len(members), PER_PULL):
            groups[(repository, 101 + index // PER_PULL)] = members[index : index + PER_PULL]
    return groups


def _unchanged(case: ReviewCase) -> ReviewCase:
    """The same thread resolved before any change was pushed (an earlier attempt)."""
    return case.model_copy(
        update={
            "head_sha": case.base_sha,
            "after_code": case.before_code,
            "unified_diff": "",
            "changed_files": [],
            "test_files": {},
            "test_files_before": {},
            "window": ResolutionWindow(
                start_commit_sha=case.base_sha,
                end_commit_sha=case.base_sha,
                subsequent_commits=[],
                flags=[WindowFlag.NO_SUBSEQUENT_COMMITS],
            ),
        }
    )


def _job(session: Session, repository: str, number: int, status: str, at: datetime) -> AdvisoryJob:
    job = AdvisoryJob(
        delivery_id=f"demo-{uuid.uuid4()}",
        task_index=0,
        event=EVENT,
        kind="pull_request",
        installation_id=DEMO_INSTALLATION,
        repository=repository,
        pull_number=number,
        status=status,
        attempts=1,
        available_at=at,
        created_at=at,
        updated_at=at,
    )
    session.add(job)
    session.flush()
    return job


def _reviewers(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(ReviewConfirmation.reviewer).where(
                ReviewConfirmation.installation_id == DEMO_INSTALLATION
            )
        )
    )


def _confirm(session: Session, repository: str, number: int, head_sha: str, at: datetime) -> None:
    session.add(
        ReviewConfirmation(
            installation_id=DEMO_INSTALLATION,
            repository=repository,
            pull_number=number,
            head_sha=head_sha,
            reviewer=f"demo-reviewer-{len(_reviewers(session)) + 1}",
            created_at=at,
        )
    )
    session.flush()
