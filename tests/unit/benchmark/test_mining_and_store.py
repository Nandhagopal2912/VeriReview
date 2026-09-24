import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from helpers.cases import make_case
from helpers.github import FakeGitHub
from verireview.benchmark import (
    GoldLabel,
    Split,
    iter_benchmark,
    iter_real_world,
    real_world_fixture,
)
from verireview.benchmark.labels import CaseAnnotation
from verireview.benchmark.manifest import FreezeError, freeze, stats, verify
from verireview.benchmark.mining import (
    LicenseNotAllowedError,
    assign_split,
    check_license,
    collect,
    find_candidates,
)
from verireview.benchmark.privacy import pseudonymise
from verireview.benchmark.store import write_gold
from verireview.contracts import CommitRef, ThreadComment, Verdict
from verireview.evaluation import evaluate
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.models import GhLicense
from verireview.verification import mvp_pipeline

REPO = RepoRef("acme/shop")
NOW = datetime(2026, 9, 1, tzinfo=UTC)
KEY = "acme__shop__7__5001"


def api(authenticated: bool = True) -> GitHubApi:
    token = SecretStr("test-token") if authenticated else None
    return GitHubApi(GitHubClient(token, transport=FakeGitHub().transport, sleep=lambda _: None))


def collected(tmp_path: Path) -> Path:
    candidates = list(find_candidates(api(), REPO))
    collect(api(), candidates, n=5, seed=1, dataset_root=tmp_path, now=NOW)
    return tmp_path


# ---------------------------------------------------------------- mining


def test_candidates_are_resolved_threads_of_merged_prs() -> None:
    found = list(find_candidates(api(), REPO))

    # PR 8 is not merged; thread 5003 is not resolved.
    assert [(c.pull_number, c.root_comment_id) for c in found] == [(7, 5001)]
    assert found[0].pr_author == "dev-alice"
    assert found[0].path == "shop/user_service.py"


def test_mining_needs_a_token() -> None:
    with pytest.raises(ValueError, match="TOKEN"):
        list(find_candidates(api(authenticated=False), REPO))


def test_license_must_be_on_the_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = api()
    assert check_license(reader, REPO).license is not None

    gpl = GhLicense.model_validate({"license": {"spdx_id": "GPL-3.0"}, "content": ""})
    monkeypatch.setattr(reader, "get_license", lambda repo: gpl)
    with pytest.raises(LicenseNotAllowedError, match="GPL-3.0"):
        check_license(reader, REPO)
    monkeypatch.setattr(reader, "get_license", lambda repo: None)
    with pytest.raises(LicenseNotAllowedError, match="not detected"):
        check_license(reader, REPO)


def test_collect_writes_a_pseudonymised_case_with_provenance_and_license(tmp_path: Path) -> None:
    root = collected(tmp_path)

    [case] = list(iter_real_world(root / "benchmark" / "real_world"))
    assert case.case_id == KEY
    assert case.provenance.license_spdx == "MIT"
    assert case.provenance.url.endswith("/pull/7#discussion_r5001")
    assert case.provenance.split == assign_split(KEY, 1, 0.5)
    authors = {c.author for c in case.case.thread.comments}
    assert authors == {"reviewer", "author"}  # rev-bob, dev-alice
    license_text = (root / "benchmark" / "LICENSES" / "acme__shop.txt").read_text(encoding="utf-8")
    assert (
        license_text.startswith("acme/shop (MIT)")
        and "Permission is hereby granted" in license_text
    )


def test_collect_skips_cases_already_collected(tmp_path: Path) -> None:
    root = collected(tmp_path)

    report = collect(api(), list(find_candidates(api(), REPO)), n=5, seed=1, dataset_root=root)

    assert report.written == [] and report.skipped == {KEY: "already collected"}


def test_split_is_deterministic_and_roughly_balanced() -> None:
    splits = [assign_split(f"case-{i}", 7, 0.5) for i in range(400)]

    assert splits == [assign_split(f"case-{i}", 7, 0.5) for i in range(400)]
    assert 150 < splits.count(Split.TEST) < 250
    assert assign_split("x", 7, 0.0) == Split.DEV and assign_split("x", 7, 1.0) == Split.TEST


# ---------------------------------------------------------------- privacy


def test_pseudonymise_replaces_logins_mentions_and_emails() -> None:
    base = make_case("x = 1\n", "x = 2\n", 1)
    comments = [
        ThreadComment(
            id=1,
            author="Rev-Bob",
            body="@dev-alice please fix; cc @carol",
            created_at=base.thread.comments[0].created_at,
        ),
        ThreadComment(
            id=2,
            author="dev-alice",
            body="done, see a@b.io\n```suggestion\n@pytest.mark.slow\n```",
            created_at=base.thread.comments[0].created_at,
        ),
        ThreadComment(
            id=3, author="carol", body="+1", created_at=base.thread.comments[0].created_at
        ),
    ]
    commit = CommitRef(
        sha="c",
        message="fix\n\nSigned-off-by: Alice <alice@example.com>",
        authored_at=None,
        committed_at=None,
        author_login="dev-alice",
    )
    case = base.model_copy(
        update={
            "thread": base.thread.model_copy(
                update={"comments": comments, "resolved_by": "rev-bob"}
            ),
            "window": base.window.model_copy(update={"subsequent_commits": [commit]}),
        }
    )

    out = pseudonymise(case, pr_author="dev-alice")

    assert [c.author for c in out.thread.comments] == ["reviewer", "author", "participant-1"]
    assert out.thread.comments[0].body == "@author please fix; cc @participant-1"
    assert (
        "<email>" in out.thread.comments[1].body
        and "@pytest.mark.slow" in out.thread.comments[1].body
    )
    assert out.thread.resolved_by == "reviewer"
    assert out.window.subsequent_commits[0].author_login == "author"
    assert "alice@example.com" not in out.window.subsequent_commits[0].message


# ---------------------------------------------------------------- store, stats, freeze


def gold(case_id: str, verdict_status: str = "satisfied", include: bool = True) -> GoldLabel:
    label = (
        CaseAnnotation.model_validate(
            {
                "case_id": case_id,
                "include": True,
                "requirements": [
                    {
                        "category": "validation",
                        "description": "check username",
                        "status": verdict_status,
                    }
                ],
                "evidence": "shop/user_service.py:3 adds the check",
            }
        )
        if include
        else CaseAnnotation(case_id=case_id, include=False, exclusion_reason="no_requirement")  # type: ignore[arg-type]
    )
    return GoldLabel(label=label, annotators=["a", "b"], agreed=True)


def test_gold_labelled_real_world_cases_are_evaluated_like_fixtures(tmp_path: Path) -> None:
    root = collected(tmp_path)
    [rw] = list(iter_real_world(root / "benchmark" / "real_world"))
    assert list(iter_benchmark(root)) == []  # no gold yet: not part of the benchmark

    write_gold(rw.directory, gold(rw.case_id))
    [case] = list(iter_benchmark(root))

    assert case.source == "real_world" and case.split == rw.provenance.split
    fixture = real_world_fixture(next(iter_real_world(root / "benchmark" / "real_world")))
    assert fixture.meta.expected_verdict == Verdict.SATISFIED
    report = evaluate(mvp_pipeline(), [case.fixture], root)
    assert report.metrics.n == 1


def test_excluded_cases_stay_out_of_the_benchmark(tmp_path: Path) -> None:
    root = collected(tmp_path)
    [rw] = list(iter_real_world(root / "benchmark" / "real_world"))
    write_gold(rw.directory, gold(rw.case_id, include=False))

    assert list(iter_benchmark(root)) == []
    assert stats(root).real_world.excluded == 1


def test_freeze_needs_gold_and_detects_changes(tmp_path: Path) -> None:
    root = collected(tmp_path)
    [rw] = list(iter_real_world(root / "benchmark" / "real_world"))
    provenance = json.loads((rw.directory / "provenance.json").read_text(encoding="utf-8"))
    provenance["split"] = "test"
    (rw.directory / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(FreezeError, match="without gold"):
        freeze(root, "v1", NOW)
    write_gold(rw.directory, gold(rw.case_id))
    manifest = freeze(root, "v1", NOW)

    assert manifest.real_world_test == [KEY]
    assert verify(root, manifest) == []
    write_gold(rw.directory, gold(rw.case_id, "not_satisfied"))
    assert verify(root, manifest) == ["real-world test cases changed"]


def test_very_large_files_are_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import verireview.benchmark.mining as mining

    monkeypatch.setattr(mining, "MAX_FILE_CHARS", 10)

    report = collect(api(), list(find_candidates(api(), REPO)), n=5, seed=1, dataset_root=tmp_path)

    assert report.written == [] and report.skipped[KEY].startswith("file_too_large")


def test_bot_accounts_are_excluded_even_without_a_bot_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 9b finding: GitHub's Copilot reviewer has the login 'Copilot' (no '[bot]'); only
    the account type says it is a bot. 8 of the first 9 collected cases were such reviews."""
    reader = api()
    real = reader.list_review_comments

    def as_copilot(repo: RepoRef, number: int) -> list[Any]:
        out = []
        for c in real(repo, number):
            if c.id == 5001:
                user = c.user.model_copy(update={"login": "Copilot", "type": "Bot"})  # type: ignore[union-attr]
                c = c.model_copy(update={"user": user})
            out.append(c)
        return out

    monkeypatch.setattr(reader, "list_review_comments", as_copilot)

    assert list(find_candidates(reader, REPO)) == []
