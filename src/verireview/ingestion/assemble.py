"""Assemble a ReviewCase for one review thread: thread + window + before/after code + diff."""

import difflib
import logging
from datetime import UTC, datetime
from pathlib import PurePosixPath

from verireview.contracts import ChangedFile, ReviewCase, WindowFlag
from verireview.gh.api import GitHubReader, RepoRef
from verireview.gh.models import GhChangedFile
from verireview.ingestion.anchor import locate_comment_line
from verireview.ingestion.window import build_window
from verireview.threads import find_thread, reconstruct_threads

logger = logging.getLogger(__name__)

FORCE_PUSH_EVENT = "head_ref_force_pushed"
MAX_TEST_FILES = 20


def ingest_review_case(
    reader: GitHubReader, repo: RepoRef, pull_number: int, comment_id: int
) -> ReviewCase:
    """Reconstruct the review thread containing ``comment_id`` and its resolution window."""
    pull = reader.get_pull(repo, pull_number)
    states = reader.list_thread_states(repo, pull_number) if reader.can_read_thread_state else None
    threads = reconstruct_threads(reader.list_review_comments(repo, pull_number), states)
    thread = find_thread(threads, comment_id)

    force_pushes = [
        e.created_at
        for e in reader.list_timeline(repo, pull_number)
        if e.event == FORCE_PUSH_EVENT and e.created_at is not None
    ]
    window = build_window(thread, reader.list_pull_commits(repo, pull_number), force_pushes)
    flags = list(window.flags)

    changed = _changed_files(
        reader, repo, pull_number, window.start_commit_sha, window.end_commit_sha, flags
    )

    before_path = thread.path
    after_path = before_path
    for f in changed:
        if f.previous_path == before_path:
            after_path = f.path
            flags.append(WindowFlag.FILE_RENAMED)
            break

    before_code = _normalise(reader.get_file(repo, before_path, window.start_commit_sha))
    anchor_line: int | None = None
    if before_code is None:
        flags.append(WindowFlag.BEFORE_CODE_UNAVAILABLE)
    elif thread.side != "LEFT":
        anchor_line = locate_comment_line(
            before_code, thread.diff_hunk, thread.side, thread.original_line
        )
        if anchor_line is None:
            flags.append(WindowFlag.ANCHOR_NOT_FOUND)
        elif anchor_line != thread.original_line:
            flags.append(WindowFlag.ANCHOR_LINE_MISMATCH)
    after_code = _normalise(reader.get_file(repo, after_path, window.end_commit_sha))
    if after_code is None and before_code is not None:
        flags.append(WindowFlag.FILE_DELETED)

    test_files: dict[str, str] = {}
    for f in changed:
        # Only the PR's own test changes; upstream (base-drift) tests are not evidence.
        if f.is_test and f.in_pr and f.status != "removed" and len(test_files) < MAX_TEST_FILES:
            content = _normalise(reader.get_file(repo, f.path, window.end_commit_sha))
            if content is not None:
                test_files[f.path] = content

    return ReviewCase(
        case_id=ReviewCase.make_case_id(repo.full_name, pull.number, thread.root_comment_id),
        repository=repo.full_name,
        pull_number=pull.number,
        pull_title=pull.title,
        base_sha=pull.base.sha,
        head_sha=pull.head.sha,
        thread=thread,
        window=window.model_copy(update={"flags": _dedupe(flags)}),
        file_path=after_path,
        before_code=before_code,
        anchor_line=anchor_line,
        after_code=after_code,
        unified_diff=make_unified_diff(before_code, after_code, before_path, after_path),
        changed_files=changed,
        test_files=test_files,
        ingested_at=datetime.now(UTC),
    )


def make_unified_diff(
    before: str | None, after: str | None, before_path: str, after_path: str
) -> str:
    """Git-style unified diff (3 lines of context); '' when nothing changed or no code exists."""
    if before is None and after is None:
        return ""
    lines = difflib.unified_diff(
        (before or "").splitlines(keepends=True),
        (after or "").splitlines(keepends=True),
        fromfile=f"a/{before_path}" if before is not None else "/dev/null",
        tofile=f"b/{after_path}" if after is not None else "/dev/null",
    )
    return "".join(_ensure_newline(line) for line in lines)


def is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    if p.suffix != ".py":
        return False
    return (
        p.name.startswith("test_")
        or p.name.endswith("_test.py")
        or p.name == "conftest.py"
        or any(part in {"test", "tests"} for part in p.parts[:-1])
    )


def _changed_files(
    reader: GitHubReader,
    repo: RepoRef,
    pull_number: int,
    start: str,
    end: str,
    flags: list[WindowFlag],
) -> list[ChangedFile]:
    """Files changed within the window, each marked with whether the PR itself changes it.

    A compare across a rebase or a merge of the base branch also contains upstream changes
    (live check: pallets/click#2622 listed 15 unrelated test files). The PR's own file list
    tells them apart.
    """
    if start == end:
        return []
    pr_files = reader.list_pull_files(repo, pull_number)
    raw: list[GhChangedFile] | None = reader.compare_files(repo, start, end)
    if raw is None:
        # Start commit unreachable (e.g. force-push): the whole PR's files are the best we have.
        flags.append(WindowFlag.CHANGED_FILES_FROM_WHOLE_PR)
        raw = pr_files
    in_pr = {f.filename for f in pr_files}
    changed = [
        ChangedFile(
            path=f.filename,
            status=f.status,
            previous_path=f.previous_filename,
            is_test=is_test_path(f.filename),
            in_pr=f.filename in in_pr,
        )
        for f in raw
    ]
    if any(not f.in_pr for f in changed):
        flags.append(WindowFlag.BASE_DRIFT_POSSIBLE)
    return changed


def _normalise(code: str | None) -> str | None:
    """LF line endings everywhere, so diffs and line numbers are platform-independent."""
    return None if code is None else code.replace("\r\n", "\n")


def _ensure_newline(line: str) -> str:
    # A last line without a trailing newline would otherwise run into the next diff line.
    return line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"


def _dedupe(flags: list[WindowFlag]) -> list[WindowFlag]:
    return list(dict.fromkeys(flags))
