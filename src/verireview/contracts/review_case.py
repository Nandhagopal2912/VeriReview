"""ReviewCase: everything the verifier needs about one review thread and its resolution.

Produced by GitHub ingestion (Phase 1) and by the fixture loader (Phase 2). Every downstream
component consumes this model, so changes must bump ``SCHEMA_VERSION``.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# v2 (Phase 1 live check): ambiguous_rewritten_commits, ChangedFile.in_pr, anchor_line, new flags.
SCHEMA_VERSION = "2"


class CommitRef(BaseModel):
    sha: str
    message: str
    authored_at: datetime | None
    committed_at: datetime | None
    author_login: str | None = None


class ThreadComment(BaseModel):
    id: int
    author: str | None
    body: str
    created_at: datetime
    in_reply_to_id: int | None = None


class ReviewThread(BaseModel):
    """A root review comment plus its replies, in chronological order."""

    root_comment_id: int
    path: str
    line: int | None = Field(
        description="Line in the current diff; None when the thread is outdated."
    )
    original_line: int | None = Field(description="Line in the commit the comment was written on.")
    start_line: int | None = None
    original_start_line: int | None = None
    side: str | None = None
    diff_hunk: str
    original_commit_sha: str = Field(description="Commit the reviewer commented on.")
    commit_sha: str = Field(description="Commit the comment position currently refers to.")
    comments: list[ThreadComment]
    is_resolved: bool | None = Field(description="None when resolution state is unknown.")
    resolved_by: str | None = None
    is_outdated: bool | None = None

    @property
    def root(self) -> ThreadComment:
        return self.comments[0]


class WindowFlag(StrEnum):
    """Caveats about how reliable the reconstructed resolution window is."""

    RESOLUTION_STATE_UNKNOWN = "resolution_state_unknown"
    RESOLUTION_TIME_UNKNOWN = "resolution_time_unknown"
    HISTORY_REWRITTEN = "history_rewritten"
    ORIGINAL_COMMIT_NOT_IN_PR = "original_commit_not_in_pr"
    ORDERED_BY_TIMESTAMP = "ordered_by_timestamp"
    PRE_COMMENT_COMMITS_EXCLUDED = "pre_comment_commits_excluded"
    NO_SUBSEQUENT_COMMITS = "no_subsequent_commits"
    COMMIT_LIST_TRUNCATED = "commit_list_truncated"
    BEFORE_CODE_UNAVAILABLE = "before_code_unavailable"
    FILE_DELETED = "file_deleted"
    FILE_RENAMED = "file_renamed"
    CHANGED_FILES_FROM_WHOLE_PR = "changed_files_from_whole_pr"
    AMBIGUOUS_REWRITTEN_COMMITS = "ambiguous_rewritten_commits"
    BASE_DRIFT_POSSIBLE = "base_drift_possible"
    ANCHOR_LINE_MISMATCH = "anchor_line_mismatch"
    ANCHOR_NOT_FOUND = "anchor_not_found"


class ResolutionWindow(BaseModel):
    """Commits made after the review comment, up to the end of the window.

    ``start_commit_sha`` is the reviewed commit (the "before" state); ``end_commit_sha`` is the
    last commit considered (the "after" state).
    """

    start_commit_sha: str
    end_commit_sha: str
    subsequent_commits: list[CommitRef]
    ambiguous_rewritten_commits: list[CommitRef] = Field(
        default_factory=list,
        description="History rewritten: authored before but committed after the comment "
        "(rebased old work or an amended response; cannot tell which).",
    )
    excluded_pre_comment_commits: list[CommitRef] = Field(default_factory=list)
    flags: list[WindowFlag] = Field(default_factory=list)


class ChangedFile(BaseModel):
    path: str
    status: str
    previous_path: str | None = None
    is_test: bool = False
    in_pr: bool = Field(
        default=True,
        description="Also changed by the PR itself. False = changed in the window only because "
        "upstream commits were merged/rebased in (base drift).",
    )


class ReviewCase(BaseModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str = Field(description="'<owner>/<repo>#<pr>/<root comment id>'")
    repository: str = Field(description="'<owner>/<repo>'")
    pull_number: int
    pull_title: str
    base_sha: str
    head_sha: str
    thread: ReviewThread
    window: ResolutionWindow
    file_path: str = Field(description="Commented file's path at the end of the window.")
    before_code: str | None
    anchor_line: int | None = Field(
        default=None,
        description="1-based line in before_code the comment points at, found by matching "
        "diff_hunk text. Prefer this over thread.original_line, which GitHub sometimes "
        "reports inconsistently with the commit content.",
    )
    after_code: str | None
    unified_diff: str = Field(description="before_code → after_code for file_path ('' if none).")
    changed_files: list[ChangedFile]
    test_files: dict[str, str] = Field(
        default_factory=dict, description="Changed test files: path → contents at window end."
    )
    ingested_at: datetime

    @staticmethod
    def make_case_id(repository: str, pull_number: int, root_comment_id: int) -> str:
        return f"{repository}#{pull_number}/{root_comment_id}"
