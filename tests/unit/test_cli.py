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
    assert payload["schema_version"] == "2"


def test_ingest_prints_non_ascii_json(capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    # Live check: printing a comment containing e.g. "→" crashed on a cp1252 console.
    assert cli.main(["ingest", "acme/shop", "7", "--comment-id", "5001", "--no-db"]) == 0

    out = capsysbinary.readouterr().out.decode("utf-8")
    assert json.loads(out)["case_id"] == "acme/shop#7/5001"
    assert "Good point → will do." in out


def test_invalid_repo_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["threads", "not-a-repo", "7"]) == 2
    assert "owner/repo" in capsys.readouterr().err


def test_unknown_comment_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["ingest", "acme/shop", "7", "--comment-id", "1", "--no-db"]) == 1
    assert "No review thread contains comment 1" in capsys.readouterr().err


FIXTURES = Path(__file__).resolve().parents[2] / "dataset" / "fixtures"


def test_verify_fixture_prints_explanation(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["verify-fixture", str(FIXTURES / "validation-001-none-check")]) == 0

    captured = capsys.readouterr()
    assert "Review request:" in captured.out
    assert "Result:\nSATISFIED" in captured.out
    assert "expected: SATISFIED" in captured.err


def test_verify_case_accepts_an_ingested_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_file = tmp_path / "case.json"
    cli.main(
        ["ingest", "acme/shop", "7", "--comment-id", "5001", "--no-db", "--out", str(case_file)]
    )
    capsys.readouterr()

    assert cli.main(["verify-case", str(case_file), "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["case_id"] == "acme/shop#7/5001"
    assert result["verdict"] in {"SATISFIED", "PARTIALLY_SATISFIED", "NOT_SATISFIED", "UNCERTAIN"}


def test_eval_fixtures_writes_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "report.json"

    assert cli.main(["eval-fixtures", "--root", str(FIXTURES), "--out", str(out)]) == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["metrics"]["n"] == len(list(FIXTURES.glob("*/meta.json")))
    assert len(report["dataset_hash"]) == 64
    assert "accuracy" in capsys.readouterr().out


def test_pipeline_can_be_selected(tmp_path: Path) -> None:
    out = tmp_path / "report.json"

    assert (
        cli.main(
            [
                "eval-fixtures",
                "--root",
                str(FIXTURES),
                "--pipeline",
                "phase2-locality",
                "--out",
                str(out),
            ]
        )
        == 0
    )

    assert json.loads(out.read_text(encoding="utf-8"))["pipeline_version"] == "phase2-locality-1"


def test_extract_prints_structured_requirements(capsys: pytest.CaptureFixture[str]) -> None:
    comment = "Please validate username, return HTTP 400 on invalid input, and add a test."

    assert cli.main(["extract", comment]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [r["category"] for r in payload["requirements"]] == [
        "validation",
        "api_behavior",
        "testing",
    ]


def test_eval_requirements_reports_both_sets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "req.json"
    heldout = FIXTURES.parent / "requirements" / "heldout.jsonl"

    assert (
        cli.main(
            [
                "eval-requirements",
                "--root",
                str(FIXTURES),
                "--heldout",
                str(heldout),
                "--out",
                str(out),
            ]
        )
        == 0
    )

    reports = json.loads(out.read_text(encoding="utf-8"))
    assert [r["name"] for r in reports] == ["dev fixtures", "held-out"]
    assert "category P/R/F1" in capsys.readouterr().out


def test_bad_fixture_path_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["verify-fixture", str(tmp_path / "missing")]) == 1
    assert "error:" in capsys.readouterr().err
