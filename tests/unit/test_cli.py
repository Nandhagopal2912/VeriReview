import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from helpers.github import FakeGitHub
from verireview import cli
from verireview.config import Settings
from verireview.gh.client import GitHubClient


@pytest.fixture(autouse=True)
def fake_github(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGitHub()

    def client_factory(token: SecretStr | None, **kwargs: Any) -> GitHubClient:
        return GitHubClient(token, transport=fake.transport, sleep=lambda _: None)

    monkeypatch.setattr(cli, "GitHubClient", client_factory)
    monkeypatch.setattr(
        cli, "get_settings", lambda: Settings(_env_file=None, github_token=SecretStr("t"))
    )


def test_threads_lists_each_thread(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["threads", "acme/shop", "7"]) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("5001\tresolved")
    assert lines[1].startswith("5003\topen")


def test_ingest_writes_review_case_json(tmp_path: Path) -> None:
    out = tmp_path / "case.json"

    assert (
        cli.main(["ingest", "acme/shop", "7", "--comment-id", "5001", "--no-db", "--out", str(out)])
        == 0
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["case_id"] == "acme/shop#7/5001"
    assert payload["schema_version"] == "1"


def test_invalid_repo_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["threads", "not-a-repo", "7"]) == 2
    assert "owner/repo" in capsys.readouterr().err


def test_unknown_comment_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["ingest", "acme/shop", "7", "--comment-id", "1", "--no-db"]) == 1
    assert "No review thread contains comment 1" in capsys.readouterr().err
