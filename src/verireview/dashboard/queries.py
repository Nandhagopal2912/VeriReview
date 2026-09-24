"""Read-only queries behind the dashboard pages. Nothing here writes to the database.

Every repository-level query filters on installation *and* repository, as the worker does.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verireview.db.models import (
    AdvisoryJob,
    RepositoryPolicy,
    RepositoryPolicyChange,
    ReviewConfirmation,
    VerificationAudit,
)


@dataclass(frozen=True)
class RepositoryRow:
    installation_id: int
    repository: str
    verifications: int
    pull_requests: int
    last_verified: datetime
    stage: str  # "advisory (default)" when not opted in


@dataclass(frozen=True)
class PullRow:
    number: int
    threads: int
    verdicts: dict[str, int]
    last_verified: datetime
    head_sha: str


@dataclass
class ThreadHistory:
    comment_id: int
    latest: VerificationAudit
    earlier: list[VerificationAudit] = field(default_factory=list)


def repositories(session: Session) -> list[RepositoryRow]:
    grouped = session.execute(
        select(
            VerificationAudit.installation_id,
            VerificationAudit.repository,
            func.count(VerificationAudit.id),
            func.count(func.distinct(VerificationAudit.pull_number)),
            func.max(VerificationAudit.created_at),
        )
        .group_by(VerificationAudit.installation_id, VerificationAudit.repository)
        .order_by(func.max(VerificationAudit.created_at).desc())
    ).all()
    stages = {
        (p.installation_id, p.repository): p.stage
        for p in session.scalars(select(RepositoryPolicy)).all()
    }
    return [
        RepositoryRow(
            installation_id=inst,
            repository=repo,
            verifications=count,
            pull_requests=pulls,
            last_verified=last,
            stage=stages.get((inst, repo), "advisory (default)"),
        )
        for inst, repo, count, pulls, last in grouped
    ]


def verdict_totals(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(VerificationAudit.verdict, func.count(VerificationAudit.id)).group_by(
            VerificationAudit.verdict
        )
    ).all()
    return {verdict: count for verdict, count in rows}


def job_totals(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(AdvisoryJob.status, func.count(AdvisoryJob.id)).group_by(AdvisoryJob.status)
    ).all()
    return {status: count for status, count in rows}


def policy(session: Session, installation_id: int, repository: str) -> RepositoryPolicy | None:
    return session.scalars(
        select(RepositoryPolicy).where(
            RepositoryPolicy.installation_id == installation_id,
            RepositoryPolicy.repository == repository,
        )
    ).first()


def policy_changes(
    session: Session, installation_id: int, repository: str
) -> list[RepositoryPolicyChange]:
    return list(
        session.scalars(
            select(RepositoryPolicyChange)
            .where(
                RepositoryPolicyChange.installation_id == installation_id,
                RepositoryPolicyChange.repository == repository,
            )
            .order_by(RepositoryPolicyChange.id.desc())
        )
    )


def confirmations(
    session: Session, installation_id: int, repository: str, limit: int = 50
) -> list[ReviewConfirmation]:
    return list(
        session.scalars(
            select(ReviewConfirmation)
            .where(
                ReviewConfirmation.installation_id == installation_id,
                ReviewConfirmation.repository == repository,
            )
            .order_by(ReviewConfirmation.id.desc())
            .limit(limit)
        )
    )


def _audits(
    session: Session, installation_id: int, repository: str, pull_number: int | None = None
) -> list[VerificationAudit]:
    query = select(VerificationAudit).where(
        VerificationAudit.installation_id == installation_id,
        VerificationAudit.repository == repository,
    )
    if pull_number is not None:
        query = query.where(VerificationAudit.pull_number == pull_number)
    return list(session.scalars(query.order_by(VerificationAudit.id.desc())))


def pulls(session: Session, installation_id: int, repository: str) -> list[PullRow]:
    latest: dict[tuple[int, int], VerificationAudit] = {}
    for row in _audits(session, installation_id, repository):
        latest.setdefault((row.pull_number, row.comment_id), row)
    by_pull: dict[int, list[VerificationAudit]] = {}
    for (number, _), row in latest.items():
        by_pull.setdefault(number, []).append(row)
    result = []
    for number, rows in by_pull.items():
        newest = max(rows, key=lambda r: r.created_at)
        result.append(
            PullRow(
                number=number,
                threads=len(rows),
                verdicts=dict(Counter(r.verdict for r in rows)),
                last_verified=newest.created_at,
                head_sha=newest.head_sha,
            )
        )
    return sorted(result, key=lambda p: p.last_verified, reverse=True)


def threads(
    session: Session, installation_id: int, repository: str, pull_number: int
) -> list[ThreadHistory]:
    histories: dict[int, ThreadHistory] = {}
    for row in _audits(session, installation_id, repository, pull_number):
        history = histories.get(row.comment_id)
        if history is None:
            histories[row.comment_id] = ThreadHistory(row.comment_id, row)
        else:
            history.earlier.append(row)
    return sorted(histories.values(), key=lambda h: h.comment_id)


def audit(session: Session, audit_id: int) -> VerificationAudit | None:
    return session.get(VerificationAudit, audit_id)


def recent_jobs(session: Session, limit: int = 100) -> list[AdvisoryJob]:
    return list(session.scalars(select(AdvisoryJob).order_by(AdvisoryJob.id.desc()).limit(limit)))
