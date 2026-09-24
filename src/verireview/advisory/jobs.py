"""PostgreSQL job queue and audit trail for advisory mode.

The queue is a table, not another service: a webhook inserts rows, workers claim them with
``SELECT … FOR UPDATE SKIP LOCKED`` (several workers never take the same job), and failed jobs
are retried with exponential backoff up to ``max_attempts``. Redelivered webhooks (same
``X-GitHub-Delivery``) insert nothing: ``ON CONFLICT DO NOTHING`` on the delivery id.

Every audit query filters on installation *and* repository (repository isolation, plan §22).
"""

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from verireview.advisory.webhooks import AdvisoryTask
from verireview.contracts import ReviewCase, VerificationResult
from verireview.db.models import AdvisoryJob, ReviewConfirmation, VerificationAudit
from verireview.policy import PolicyDecision

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
MAX_ERROR_CHARS = 500


def enqueue(session: Session, delivery_id: str, event: str, tasks: list[AdvisoryTask]) -> int:
    """Insert the delivery's tasks; returns how many were new (0 for a redelivery)."""
    created = 0
    for index, task in enumerate(tasks):
        statement = (
            insert(AdvisoryJob)
            .values(
                delivery_id=delivery_id,
                task_index=index,
                event=event,
                kind=task.kind,
                installation_id=task.installation_id,
                repository=task.repository,
                pull_number=task.pull_number,
                comment_id=task.comment_id,
                head_sha=task.head_sha,
                actor=task.actor,
                status=QUEUED,
                attempts=0,
            )
            .on_conflict_do_nothing(index_elements=["delivery_id", "task_index"])
            .returning(AdvisoryJob.id)
        )
        created += session.execute(statement).first() is not None
    session.commit()
    return created


def claim(session: Session) -> AdvisoryJob | None:
    """Take the oldest available job (skipping rows another worker has locked)."""
    job = session.scalars(
        select(AdvisoryJob)
        .where(AdvisoryJob.status == QUEUED, AdvisoryJob.available_at <= func.now())
        .order_by(AdvisoryJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is None:
        session.rollback()
        return None
    job.status = RUNNING
    job.attempts += 1
    job.updated_at = datetime.now(UTC)
    session.commit()
    return job


def complete(session: Session, job: AdvisoryJob) -> None:
    job.status = DONE
    job.last_error = None
    job.updated_at = datetime.now(UTC)
    session.commit()


def retry_or_fail(
    session: Session, job: AdvisoryJob, error: str, max_attempts: int, permanent: bool = False
) -> None:
    """Retry later (backoff 30 s, 60 s, 120 s, …) or give up after ``max_attempts``."""
    job.last_error = error[:MAX_ERROR_CHARS]
    job.updated_at = datetime.now(UTC)
    if permanent or job.attempts >= max_attempts:
        job.status = FAILED
    else:
        job.status = QUEUED
        job.available_at = datetime.now(UTC) + timedelta(seconds=30 * 2 ** (job.attempts - 1))
    session.commit()


# ---------------------------------------------------------------- audit trail


def inputs_sha256(case: ReviewCase) -> str:
    """Hash of exactly what was verified: the ReviewCase JSON (thread, window, code, tests)."""
    return hashlib.sha256(case.model_dump_json().encode("utf-8")).hexdigest()


def record_audit(
    session: Session,
    job: AdvisoryJob,
    case: ReviewCase,
    comment_id: int,
    result: VerificationResult,
    decision: PolicyDecision,
) -> VerificationAudit:
    row = VerificationAudit(
        job_id=job.id,
        installation_id=job.installation_id,
        repository=job.repository,
        pull_number=job.pull_number,
        comment_id=comment_id,
        head_sha=case.head_sha,
        inputs_sha256=inputs_sha256(case),
        pipeline_version=result.pipeline_version,
        verdict=result.verdict.value,
        confidence=result.confidence.value,
        action=decision.action.value,
        result=result.model_dump(mode="json"),
        review_case=case.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    return row


def latest_results(
    session: Session, installation_id: int, repository: str, pull_number: int, head_sha: str
) -> list[VerificationAudit]:
    """The newest verification of each thread at ``head_sha``, for this repository only."""
    rows = session.scalars(
        select(VerificationAudit)
        .where(
            VerificationAudit.installation_id == installation_id,
            VerificationAudit.repository == repository,
            VerificationAudit.pull_number == pull_number,
            VerificationAudit.head_sha == head_sha,
        )
        .order_by(VerificationAudit.id.desc())
    ).all()
    latest: dict[int, VerificationAudit] = {}
    for row in rows:
        latest.setdefault(row.comment_id, row)
    return sorted(latest.values(), key=lambda r: r.comment_id)


def record_confirmation(session: Session, job: AdvisoryJob) -> bool:
    """Store "reviewer X confirmed the result at head H" once; returns whether it was new."""
    if job.actor is None or job.head_sha is None:
        raise ValueError("a confirmation needs a reviewer and a head commit")
    statement = (
        insert(ReviewConfirmation)
        .values(
            installation_id=job.installation_id,
            repository=job.repository,
            pull_number=job.pull_number,
            head_sha=job.head_sha,
            reviewer=job.actor,
        )
        .on_conflict_do_nothing(
            index_elements=["installation_id", "repository", "head_sha", "reviewer"]
        )
        .returning(ReviewConfirmation.id)
    )
    new = session.execute(statement).first() is not None
    session.commit()
    return new


def confirmations(
    session: Session, installation_id: int, repository: str, head_sha: str
) -> list[str]:
    """Reviewers who confirmed the result at ``head_sha`` (this repository only)."""
    return list(
        session.scalars(
            select(ReviewConfirmation.reviewer)
            .where(
                ReviewConfirmation.installation_id == installation_id,
                ReviewConfirmation.repository == repository,
                ReviewConfirmation.head_sha == head_sha,
            )
            .order_by(ReviewConfirmation.id)
        )
    )


def purge_stored_cases(session: Session, older_than_days: int) -> int:
    """Remove stored review cases (repository code) from audit rows older than the retention.

    The verdict, hashes and result stay (the audit trail); only the copied code and diff go.
    Returns how many rows were purged.
    """
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    rows = session.scalars(
        select(VerificationAudit).where(
            VerificationAudit.created_at < cutoff, VerificationAudit.review_case.is_not(None)
        )
    ).all()
    for row in rows:
        row.review_case = None
    session.commit()
    return len(rows)
