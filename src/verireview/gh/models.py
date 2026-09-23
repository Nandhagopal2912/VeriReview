"""Typed subsets of GitHub API responses. Unknown fields are ignored.

Commit author e-mail addresses are deliberately not modelled, so they are never stored.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _GhModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class GhUser(_GhModel):
    login: str


class GhRef(_GhModel):
    ref: str
    sha: str


class GhPullRequest(_GhModel):
    number: int
    title: str
    state: str
    html_url: str
    user: GhUser | None = None
    base: GhRef
    head: GhRef
    merged_at: datetime | None = None


class GhReviewComment(_GhModel):
    """``GET /repos/{owner}/{repo}/pulls/{n}/comments`` item."""

    id: int
    pull_request_review_id: int | None = None
    in_reply_to_id: int | None = None
    path: str
    line: int | None = None
    original_line: int | None = None
    start_line: int | None = None
    original_start_line: int | None = None
    side: str | None = None
    commit_id: str
    original_commit_id: str
    diff_hunk: str
    body: str
    user: GhUser | None = None
    created_at: datetime
    updated_at: datetime | None = None


class GhSignature(_GhModel):
    name: str | None = None
    date: datetime | None = None


class GhCommitDetail(_GhModel):
    message: str
    author: GhSignature | None = None
    committer: GhSignature | None = None


class GhCommit(_GhModel):
    """``GET /repos/{owner}/{repo}/pulls/{n}/commits`` item (oldest first, max 250)."""

    sha: str
    commit: GhCommitDetail
    author: GhUser | None = None


class GhTimelineEvent(_GhModel):
    """``GET /repos/{owner}/{repo}/issues/{n}/timeline`` item (only the fields we use)."""

    event: str | None = None
    created_at: datetime | None = None


class GhChangedFile(_GhModel):
    """File entry of the compare API or ``GET .../pulls/{n}/files``."""

    filename: str
    status: str
    previous_filename: str | None = None


class GhThreadState(_GhModel):
    """Resolution state of one review thread (GraphQL ``PullRequestReviewThread``)."""

    root_comment_id: int
    is_resolved: bool
    is_outdated: bool
    resolved_by: str | None = None


class GhLicenseInfo(_GhModel):
    spdx_id: str | None = None
    name: str | None = None


class GhLicense(_GhModel):
    """``GET /repos/{owner}/{repo}/license``: the detected license and its text (base64)."""

    license: GhLicenseInfo | None = None
    content: str = ""
    encoding: str = "base64"
    html_url: str | None = None
