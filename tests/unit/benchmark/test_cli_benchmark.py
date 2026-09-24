import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from helpers.github import FakeGitHub
from verireview import cli, cli_benchmark
from verireview.config import Settings
from verireview.gh.client import GitHubClient

DATASET = Path(__file__).resolve().parents[3] / "dataset"
KEY = "acme__shop__7__5001"
VERSIONED = {
    "benchmark-stats",
    "collect-cases",
    "annotation-sheet",
    "adjudication-sheet",
    "build-gold",
    "benchmark-freeze",
    "eval-benchmark",
}


def main_v1(args: list[str]) -> int:
    """These tests use the v1 layout (real-world cases under benchmark/real_world)."""
    return cli.main([*args, "--benchmark-version", "v1"] if args[0] in VERSIONED else args)


@pytest.fixture(autouse=True)
def fake_github(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGitHub()

    def client_factory(token: SecretStr | None, **kwargs: Any) -> GitHubClient:
        return GitHubClient(token, transport=fake.transport, sleep=lambda _: None)

    monkeypatch.setattr(cli_benchmark, "GitHubClient", client_factory)
    monkeypatch.setattr(
        cli_benchmark, "get_settings", lambda: Settings(_env_file=None, github_token=SecretStr("t"))
    )


def mine_and_collect(tmp_path: Path) -> Path:
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "repositories.json").write_text(
        json.dumps({"approved_by": "owner", "repositories": ["acme/shop"]}), encoding="utf-8"
    )
    candidates = tmp_path / "candidates.jsonl"
    args = ["mine-candidates", "acme/shop", "--dataset", str(tmp_path), "--out", str(candidates)]
    assert main_v1(args) == 0
    assert (
        main_v1(
            [
                "collect-cases",
                str(candidates),
                "--n",
                "5",
                "--seed",
                "3",
                "--dataset",
                str(tmp_path),
            ]
        )
        == 0
    )
    return tmp_path


def export(path: Path, annotator: str, status: str) -> Path:
    body = {
        "annotator": annotator,
        "batch": "rw",
        "sheet_version": "phase9-sheet-1",
        "annotations": [
            {
                "case_id": KEY,
                "include": True,
                "requirements": [
                    {"category": "validation", "description": "check username", "status": status}
                ],
            }
        ],
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_benchmark_stats_on_the_real_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    assert main_v1(["benchmark-stats", "--dataset", str(DATASET)]) == 0

    out = capsys.readouterr().out
    assert "controlled/test 60" in out and "adversarial/test 40" in out
    assert "✓ test cases: naming" in out


def test_mining_refuses_an_unapproved_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main_v1(["mine-candidates", "acme/shop", "--dataset", str(tmp_path)]) == 2
    assert "not approved" in capsys.readouterr().err


def test_full_annotation_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = mine_and_collect(tmp_path)
    sheet = tmp_path / "sheet.html"
    assert (
        main_v1(["annotation-sheet", "--batch", "rw", "--dataset", str(root), "--out", str(sheet)])
        == 0
    )
    assert KEY in sheet.read_text(encoding="utf-8")

    a = export(tmp_path / "a.json", "ann-a", "satisfied")
    b = export(tmp_path / "b.json", "ann-b", "not_satisfied")
    assert main_v1(["agreement", str(a), str(b), "--out", str(tmp_path / "agree.json")]) == 0
    assert "disagreements to adjudicate: 1" in capsys.readouterr().out

    assert main_v1(["build-gold", str(a), str(b), "--dataset", str(root)]) == 1
    assert "need a decision" in capsys.readouterr().err

    adj_sheet = tmp_path / "adj.html"
    assert (
        main_v1(
            [
                "adjudication-sheet",
                str(a),
                str(b),
                "--batch",
                "rw",
                "--dataset",
                str(root),
                "--out",
                str(adj_sheet),
            ]
        )
        == 0
    )
    adjudication = tmp_path / "adj.json"
    adjudication.write_text(
        json.dumps(
            {
                "adjudicator": "judge",
                "decisions": [{"case_id": KEY, "chosen": "a", "reason": "check is present"}],
            }
        ),
        encoding="utf-8",
    )
    assert (
        main_v1(
            [
                "build-gold",
                str(a),
                str(b),
                "--adjudication",
                str(adjudication),
                "--dataset",
                str(root),
            ]
        )
        == 0
    )
    gold = json.loads(
        (root / "benchmark" / "real_world" / KEY / "gold.json").read_text(encoding="utf-8")
    )
    assert gold["label"]["verdict"] == "SATISFIED" and gold["adjudicator"] == "judge"

    assert main_v1(["benchmark-freeze", "--dataset", str(root)]) == 0
    manifest = json.loads((root / "benchmark" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "v1"


def test_calibration_sheet(tmp_path: Path) -> None:
    out = tmp_path / "cal.html"

    assert (
        main_v1(
            [
                "annotation-sheet",
                "--batch",
                "cal",
                "--calibration",
                "--dataset",
                str(DATASET),
                "--out",
                str(out),
            ]
        )
        == 0
    )

    html = out.read_text(encoding="utf-8")
    assert html.count('"reference": {') == 10


def test_provisional_model_gold_never_replaces_human_gold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = mine_and_collect(tmp_path)
    claude = export(tmp_path / "claude.json", "claude", "not_satisfied")
    gold_path = root / "benchmark" / "real_world" / KEY / "gold.json"

    assert main_v1(["build-gold", str(claude), "--dataset", str(root)]) == 2  # source required
    args = ["build-gold", str(claude), "--single-source", "model", "--dataset", str(root)]
    assert main_v1(args) == 0
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    assert gold["label_source"] == "model" and gold["annotators"] == ["claude"]
    assert main_v1(["benchmark-stats", "--dataset", str(root)]) == 0
    assert "provisional model 1" in capsys.readouterr().out

    a = export(tmp_path / "a.json", "ann-a", "satisfied")
    b = export(tmp_path / "b.json", "ann-b", "satisfied")
    assert main_v1(["build-gold", str(a), str(b), "--dataset", str(root)]) == 0
    assert json.loads(gold_path.read_text(encoding="utf-8"))["label_source"] == "human"

    assert main_v1(args) == 0  # the model label comes back...
    assert "kept human gold" in capsys.readouterr().out  # ...but does not overwrite humans
    assert json.loads(gold_path.read_text(encoding="utf-8"))["label_source"] == "human"
