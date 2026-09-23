"""Hand-written dev fixtures → ReviewCase.

Layout of one fixture (``dataset/fixtures/<case_id>/``)::

    comment.txt     the reviewer's comment
    before.py       the commented file when the comment was written
    after.py        the same file at the end of the resolution window
    meta.json       FixtureMeta: target, expected verdict, gold requirements, rationale
    tests_before/   optional: test files before (paths mirror the repository)
    tests_after/    optional: test files after

The loader produces the same ReviewCase that GitHub ingestion does, so every downstream stage
runs identically on fixtures and on real pull requests.
"""

import hashlib
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from verireview.contracts import (
    ChangedFile,
    CommitRef,
    Requirement,
    RequirementCategory,
    ResolutionWindow,
    ReviewCase,
    ReviewRequirement,
    ReviewThread,
    ThreadComment,
    Verdict,
    WindowFlag,
)
from verireview.ingestion import make_unified_diff
from verireview.ingestion.assemble import is_test_path

FIXTURE_REPOSITORY = "fixtures/dev"
_HUNK_CONTEXT = 3
# Fixed timestamps keep loaded cases (and results) byte-for-byte reproducible.
_COMMENT_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_COMMIT_AT = datetime(2026, 1, 1, 13, 0, tzinfo=UTC)


class HardCase(StrEnum):
    """Difficult-case types from plan §18, plus a few more the dev set deliberately covers."""

    LEXICAL_FALSE_POSITIVE = "lexical_false_positive"
    PARTIAL = "partial"
    UNRELATED_CHANGE = "unrelated_change"
    PRE_EXISTING = "pre_existing"
    WRONG_TARGET = "wrong_target"
    WRONG_ORDER = "wrong_order"
    WRONG_VALUE = "wrong_value"
    AMBIGUOUS = "ambiguous"
    # Phase 9 adversarial types
    PROMPT_INJECTION = "prompt_injection"  # text addressed to the verifier instead of a fix
    STRING_MENTION = "string_mention"  # the fix is named in a string literal, not done
    COMMENTED_OUT = "commented_out"  # the fix exists only as commented-out code
    DEAD_CODE = "dead_code"  # the fix is unreachable or its result unused
    FORMATTING_ONLY = "formatting_only"  # reformatting near the target, no behaviour change
    MISLEADING_COMMENT = "misleading_comment"  # a valid fix next to a stale "TODO" comment
    UNUSUAL_IDIOM = "unusual_idiom"  # a valid fix in a less common form


class FixtureMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: RequirementCategory
    file_path: str
    target_symbol: str | None = None
    comment_line: int = Field(ge=1, description="1-based line in before.py the comment is on.")
    expected_verdict: Verdict
    hard_case: HardCase | None = None
    rationale: str = Field(min_length=10, description="Why the expected verdict is correct.")
    requirements: list[Requirement] = Field(min_length=1, description="Gold requirements.")


@dataclass(frozen=True)
class Fixture:
    meta: FixtureMeta
    case: ReviewCase
    gold_requirement: ReviewRequirement


class FixtureError(ValueError):
    pass


def load_fixture(directory: Path) -> Fixture:
    meta = FixtureMeta.model_validate_json(_read(directory / "meta.json"))
    if meta.case_id != directory.name:
        raise FixtureError(f"{directory}: meta.case_id {meta.case_id!r} != directory name")
    comment = _read(directory / "comment.txt").strip()
    before = _read(directory / "before.py")
    after = _read(directory / "after.py")
    before_lines = before.split("\n")
    if meta.comment_line > len(before_lines) or not before_lines[meta.comment_line - 1].strip():
        raise FixtureError(f"{directory}: comment_line {meta.comment_line} is not a code line")

    tests_before = _read_tree(directory / "tests_before")
    tests_after = _read_tree(directory / "tests_after")
    changed = _changed_files(meta.file_path, before, after, tests_before, tests_after)

    case_id = f"fixture/{meta.case_id}"
    start_sha = _sha("before", before, tests_before)
    changed_anything = bool(changed)
    end_sha = _sha("after", after, tests_after) if changed_anything else start_sha
    subsequent = (
        [
            CommitRef(
                sha=end_sha,
                message="Address review comment",
                authored_at=_COMMIT_AT,
                committed_at=_COMMIT_AT,
                author_login="developer",
            )
        ]
        if changed_anything
        else []
    )
    flags = [] if changed_anything else [WindowFlag.NO_SUBSEQUENT_COMMITS]
    root_id = zlib.crc32(case_id.encode())

    case = ReviewCase(
        case_id=case_id,
        repository=FIXTURE_REPOSITORY,
        pull_number=0,
        pull_title=meta.case_id,
        base_sha=start_sha,
        head_sha=end_sha,
        thread=ReviewThread(
            root_comment_id=root_id,
            path=meta.file_path,
            line=meta.comment_line,
            original_line=meta.comment_line,
            side="RIGHT",
            diff_hunk=_diff_hunk(before_lines, meta.comment_line),
            original_commit_sha=start_sha,
            commit_sha=end_sha,
            comments=[
                ThreadComment(id=root_id, author="reviewer", body=comment, created_at=_COMMENT_AT)
            ],
            is_resolved=True,
            is_outdated=before != after,
        ),
        window=ResolutionWindow(
            start_commit_sha=start_sha,
            end_commit_sha=end_sha,
            subsequent_commits=subsequent,
            flags=flags,
        ),
        file_path=meta.file_path,
        before_code=before,
        anchor_line=meta.comment_line,
        after_code=after,
        unified_diff=make_unified_diff(before, after, meta.file_path, meta.file_path),
        changed_files=changed,
        test_files={
            p: tests_after[p] for p in tests_after if tests_before.get(p) != tests_after[p]
        },
        test_files_before={
            p: tests_before[p]
            for p in tests_before
            if p in tests_after and tests_before[p] != tests_after[p]
        },
        ingested_at=_COMMENT_AT,
    )
    gold = ReviewRequirement(
        case_id=case_id,
        target_file=meta.file_path,
        target_symbol=meta.target_symbol,
        requirements=meta.requirements,
        # The annotation marks ambiguous requests via hard_case; gold extraction would flag them.
        ambiguity=1.0 if meta.hard_case == HardCase.AMBIGUOUS else 0.0,
        ambiguity_reasons=["annotated as ambiguous"] if meta.hard_case == HardCase.AMBIGUOUS else [],
        source="manual",
    )
    return Fixture(meta=meta, case=case, gold_requirement=gold)


def iter_fixtures(root: Path) -> Iterator[Fixture]:
    """All fixtures under ``root`` in name order (directories containing meta.json)."""
    for directory in sorted(p.parent for p in root.glob("*/meta.json")):
        yield load_fixture(directory)


def _changed_files(
    file_path: str,
    before: str,
    after: str,
    tests_before: dict[str, str],
    tests_after: dict[str, str],
) -> list[ChangedFile]:
    changed: list[ChangedFile] = []
    if before != after:
        changed.append(ChangedFile(path=file_path, status="modified"))
    for path in sorted(set(tests_before) | set(tests_after)):
        old, new = tests_before.get(path), tests_after.get(path)
        if old == new:
            continue
        status = "added" if old is None else "removed" if new is None else "modified"
        changed.append(ChangedFile(path=path, status=status, is_test=is_test_path(path)))
    return changed


def _diff_hunk(before_lines: list[str], line: int) -> str:
    """A GitHub-style hunk that ends at the commented line (as GitHub truncates it)."""
    start = max(1, line - _HUNK_CONTEXT)
    count = line - start + 1
    body = "\n".join(f" {text}" for text in before_lines[start - 1 : line])
    return f"@@ -{start},{count} +{start},{count} @@\n{body}"


def _read(path: Path) -> str:
    if not path.is_file():
        raise FixtureError(f"Missing fixture file: {path}")
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _read_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): _read(p) for p in sorted(root.rglob("*.py"))}


def _sha(label: str, code: str, tests: dict[str, str]) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(label.encode())
    digest.update(code.encode())
    for path in sorted(tests):
        digest.update(path.encode() + b"\0" + tests[path].encode())
    return digest.hexdigest()
