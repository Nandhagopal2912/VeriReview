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
