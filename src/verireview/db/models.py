"""ORM models for ingested GitHub data.

Every table hangs off ``repositories`` (directly or via ``pull_requests``) so all data is scoped
to one repository: the basis for repository isolation (plan §22).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from verireview.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("repository_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    number: Mapped[int]
    title: Mapped[str] = mapped_column(Text)
    base_sha: Mapped[str] = mapped_column(String(40))
    head_sha: Mapped[str] = mapped_column(String(40))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewThreadRow(Base):
    __tablename__ = "review_threads"
    __table_args__ = (UniqueConstraint("pull_request_id", "root_comment_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"))
    root_comment_id: Mapped[int] = mapped_column(BigInteger)
    path: Mapped[str] = mapped_column(Text)
    original_line: Mapped[int | None]
    original_commit_sha: Mapped[str] = mapped_column(String(40))
    is_resolved: Mapped[bool | None]
    is_outdated: Mapped[bool | None]
    resolved_by: Mapped[str | None] = mapped_column(String(100))


class ReviewCommentRow(Base):
    __tablename__ = "review_comments"
    __table_args__ = (UniqueConstraint("thread_id", "github_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("review_threads.id", ondelete="CASCADE"))
    github_id: Mapped[int] = mapped_column(BigInteger)
    in_reply_to_id: Mapped[int | None] = mapped_column(BigInteger)
    author: Mapped[str | None] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommitRow(Base):
    __tablename__ = "commits"
    __table_args__ = (UniqueConstraint("repository_id", "sha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    sha: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(String(100))
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewCaseRow(Base):
    """The full ReviewCase as JSON: the unit the verifier consumes."""

    __tablename__ = "review_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"))
    case_id: Mapped[str] = mapped_column(String(300), unique=True)
    schema_version: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdvisoryJob(Base):
    """One piece of advisory work from a webhook delivery (Phase 11 job queue).

    ``delivery_id`` + ``task_index`` is unique: GitHub redelivering the same event (same
    ``X-GitHub-Delivery``) creates no second job, so a delivery is processed once. Workers claim
    rows with ``FOR UPDATE SKIP LOCKED``; ``available_at`` delays retries.
    """

    __tablename__ = "advisory_jobs"
    __table_args__ = (UniqueConstraint("delivery_id", "task_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(100))
    task_index: Mapped[int] = mapped_column(default=0)
    event: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))
    installation_id: Mapped[int] = mapped_column(BigInteger)
    repository: Mapped[str] = mapped_column(String(200), index=True)
    pull_number: Mapped[int]
    comment_id: Mapped[int | None] = mapped_column(BigInteger)
    head_sha: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VerificationAudit(Base):
    """Audit trail (plan §30): every advisory verification, its inputs hash, version and result.

    Scoped by ``installation_id`` + ``repository``: every query filters on both, so one
    installation or repository never sees another's rows (repository isolation, plan §22).
    ``result`` is the full VerificationResult (verdict, per-requirement status, evidence).
    """

    __tablename__ = "verification_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("advisory_jobs.id", ondelete="SET NULL"))
    installation_id: Mapped[int] = mapped_column(BigInteger)
    repository: Mapped[str] = mapped_column(String(200), index=True)
    pull_number: Mapped[int]
    comment_id: Mapped[int] = mapped_column(BigInteger)
    head_sha: Mapped[str] = mapped_column(String(40))
    inputs_sha256: Mapped[str] = mapped_column(String(64))
    pipeline_version: Mapped[str] = mapped_column(String(60))
    verdict: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
