"""Mine real-world review threads from approved public repositories (Phase 9).

1. ``find_candidates``: merged PRs → resolved review threads on Python files, opened by someone
   other than the PR author, not by a bot, with a non-trivial comment. Needs a token: resolution
   state is GraphQL-only.
2. ``collect``: a seeded random sample of candidates → ingested ReviewCases, pseudonymised,
   written with provenance and a dev/test split fixed *before* anyone labels them.

A repository is mined only if its license is on ``ALLOWED_LICENSES`` (permissive licenses that
allow redistributing code excerpts with attribution); its license text is stored next to the data.
The repositories themselves are chosen by the project owner (roadmap D9).
"""

import base64
import hashlib
import random
import re
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from verireview.benchmark.privacy import pseudonymise
from verireview.benchmark.store import (
    LICENSES,
    REAL_WORLD,
    Provenance,
    Split,
    case_dir_name,
    write_real_world,
)
from verireview.gh.api import GitHubReader, RepoRef
from verireview.gh.errors import GitHubError
from verireview.gh.models import GhLicense, GhPullRequest
from verireview.ingestion import ingest_review_case
from verireview.threads import ThreadNotFoundError, reconstruct_threads

COLLECTOR_VERSION = "phase9-collector-1"
ALLOWED_LICENSES = frozenset(
    {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0", "0BSD"}
)
_BOT = re.compile(
    r"\[bot\]$|^(dependabot|renovate|github-actions|pre-commit-ci|codecov)\b", re.IGNORECASE
)
MIN_COMMENT_CHARS = 10


class MiningReader(GitHubReader, Protocol):
    def list_pulls(self, repo: RepoRef, max_items: int = 100) -> list[GhPullRequest]: ...

    def get_license(self, repo: RepoRef) -> GhLicense | None: ...


class LicenseNotAllowedError(Exception):
    pass


class Candidate(BaseModel):
    repository: str
    pull_number: int
    root_comment_id: int
    path: str
    pr_author: str | None
    is_outdated: bool | None
    created_at: datetime
    preview: str


class CollectReport(BaseModel):
    written: list[str]
    skipped: dict[str, str]  # candidate key → reason


def check_license(reader: MiningReader, repo: RepoRef) -> GhLicense:
    found = reader.get_license(repo)
    spdx = found.license.spdx_id if found and found.license else None
    if found is None or spdx not in ALLOWED_LICENSES:
        raise LicenseNotAllowedError(
            f"{repo}: license {spdx or 'not detected'} is not on the allowlist "
            f"{sorted(ALLOWED_LICENSES)}"
        )
    return found


def find_candidates(reader: MiningReader, repo: RepoRef, max_prs: int = 30) -> Iterator[Candidate]:
    if not reader.can_read_thread_state:
        raise ValueError("mining needs VERIREVIEW_GITHUB_TOKEN: only resolved threads qualify")
    check_license(reader, repo)
    for pull in reader.list_pulls(repo, max_items=max_prs):
        if pull.merged_at is None:
            continue
        comments = reader.list_review_comments(repo, pull.number)
        if not comments:
            continue
        states = reader.list_thread_states(repo, pull.number)
        pr_author = pull.user.login if pull.user else None
        for thread in reconstruct_threads(comments, states):
            root = thread.root
            reviewer = root.author or ""
            if (
                not thread.path.endswith(".py")
                or thread.is_resolved is not True
                or not reviewer
                or _BOT.search(reviewer)
                or (pr_author is not None and reviewer.lower() == pr_author.lower())
                or len(root.body.strip()) < MIN_COMMENT_CHARS
            ):
                continue
            yield Candidate(
                repository=repo.full_name,
                pull_number=pull.number,
                root_comment_id=thread.root_comment_id,
                path=thread.path,
                pr_author=pr_author,
                is_outdated=thread.is_outdated,
                created_at=root.created_at,
                preview=" ".join(root.body.split())[:200],
            )


def collect(
    reader: MiningReader,
    candidates: Iterable[Candidate],
    n: int,
    seed: int,
    dataset_root: Path,
    test_fraction: float = 0.5,
    now: datetime | None = None,
) -> CollectReport:
    pool = sorted(candidates, key=lambda c: (c.repository, c.pull_number, c.root_comment_id))
    random.Random(seed).shuffle(pool)  # noqa: S311 - sampling, not security
    root = dataset_root / REAL_WORLD
    licenses: dict[str, str] = {}
    written: list[str] = []
    skipped: dict[str, str] = {}
    for c in pool:
        if len(written) >= n:
            break
        key = case_dir_name(c.repository, c.pull_number, c.root_comment_id)
        if (root / key).exists():
            skipped[key] = "already collected"
            continue
        repo = RepoRef(c.repository)
        try:
            if c.repository not in licenses:
                licenses[c.repository] = _store_license(
                    check_license(reader, repo), dataset_root, repo
                )
            case = ingest_review_case(reader, repo, c.pull_number, c.root_comment_id)
        except (GitHubError, ThreadNotFoundError, LicenseNotAllowedError) as exc:
            skipped[key] = f"{type(exc).__name__}: {exc}"
            continue
        if case.before_code is None or case.after_code is None:
            skipped[key] = "window_unusable: commented file missing before or after"
            continue
        provenance = Provenance(
            repository=c.repository,
            pull_number=c.pull_number,
            root_comment_id=c.root_comment_id,
            url=f"https://github.com/{c.repository}/pull/{c.pull_number}#discussion_r{c.root_comment_id}",
            license_spdx=licenses[c.repository],
            mined_at=now or datetime.now(UTC),
            split=assign_split(key, seed, test_fraction),
            collector_version=COLLECTOR_VERSION,
        )
        write_real_world(root, pseudonymise(case, c.pr_author), provenance)
        written.append(key)
    return CollectReport(written=written, skipped=skipped)


def assign_split(key: str, seed: int, test_fraction: float) -> Split:
    """Deterministic and label-blind: depends only on the case key and the seed."""
    bucket = int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest(), 16) % 10_000
    return Split.TEST if bucket < test_fraction * 10_000 else Split.DEV


def _store_license(found: GhLicense, dataset_root: Path, repo: RepoRef) -> str:
    spdx = found.license.spdx_id if found.license else None
    assert spdx is not None  # noqa: S101 - check_license guarantees it
    text = (
        base64.b64decode(found.content).decode("utf-8", errors="replace") if found.content else ""
    )
    folder = dataset_root / LICENSES
    folder.mkdir(parents=True, exist_ok=True)
    header = f"{repo.full_name} ({spdx})\n{found.html_url or ''}\n\n"
    (folder / f"{repo.owner}__{repo.name}.txt").write_text(
        header + text, encoding="utf-8", newline="\n"
    )
    return spdx
