from pathlib import Path

import pytest

from verireview import cli
from verireview.contracts import Confidence, Verdict
from verireview.evaluation.benchmark import (
    STATISTICS,
    CaseRecord,
    bootstrap_interval,
    coverage,
    paired_difference,
    selective_accuracy,
)
from verireview.evaluation.systems import SYSTEMS

DATASET = Path(__file__).resolve().parents[3] / "dataset"
S, P, N, U = (
    Verdict.SATISFIED,
    Verdict.PARTIALLY_SATISFIED,
    Verdict.NOT_SATISFIED,
    Verdict.UNCERTAIN,
)


def rec(i: int, expected: Verdict, predicted: Verdict) -> CaseRecord:
    return CaseRecord(
        case_id=f"c{i}",
        source="controlled",
        category="validation",
        hard_case=None,
        expected=expected,
        predicted=predicted,
        confidence=Confidence.MEDIUM,
    )


RECORDS = [rec(0, S, S), rec(1, S, U), rec(2, N, N), rec(3, N, S), rec(4, P, U), rec(5, U, U)]


def test_coverage_and_selective_accuracy() -> None:
    assert coverage(RECORDS) == pytest.approx(3 / 6)
    assert selective_accuracy(RECORDS) == pytest.approx(2 / 3)  # S->S, N->N right; N->S wrong
    assert coverage([]) is None
    assert selective_accuracy([rec(0, S, U)]) is None


def test_bootstrap_interval_is_deterministic_and_brackets_the_estimate() -> None:
    first = bootstrap_interval(RECORDS, STATISTICS["accuracy"], 300)
    second = bootstrap_interval(RECORDS, STATISTICS["accuracy"], 300)

    assert first == second
    assert first.estimate == pytest.approx(3 / 6)
    assert first.low is not None and first.high is not None
    assert first.low <= first.estimate <= first.high


def test_undefined_statistic_has_no_interval() -> None:
    only_valid = [rec(0, S, S), rec(1, S, N)]

    interval = bootstrap_interval(only_valid, STATISTICS["false_acceptance_rate"], 100)

    assert interval.estimate is None and interval.low is None


def test_paired_difference_of_identical_systems_is_zero() -> None:
    diff = paired_difference(RECORDS, RECORDS, STATISTICS["accuracy"], 200)

    assert (diff.estimate, diff.low, diff.high) == (0.0, 0.0, 0.0)


def test_paired_difference_uses_the_same_cases() -> None:
    better = [rec(i, r.expected, r.expected) for i, r in enumerate(RECORDS)]

    diff = paired_difference(better, RECORDS, STATISTICS["accuracy"], 200)

    assert diff.estimate == pytest.approx(1.0 - 3 / 6)
    assert diff.low is not None and diff.low > 0


def test_the_pre_registered_systems() -> None:
    assert [s.name for s in SYSTEMS] == ["A", "B", "B'", "L", "S", "R", "C/D", "E", "F", "F-gold"]
    assert {s.name for s in SYSTEMS if s.needs_models} == {"B", "B'", "E"}


def test_the_test_split_needs_an_explicit_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["eval-benchmark", "--split", "test", "--dataset", str(DATASET)]) == 2
    assert "--final-test-run" in capsys.readouterr().err


def test_dev_run_writes_a_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "dev.json"
    args = ["eval-benchmark", "--split", "dev", "--systems", "A,F", "--resamples", "20"]
    args += ["--benchmark-version", "v1"]

    assert cli.main([*args, "--dataset", str(DATASET), "--out", str(out)]) == 0

    printed = capsys.readouterr().out
    assert "split dev: 83 cases" in printed and "vs A" in printed
    assert '"split": "dev"' in out.read_text(encoding="utf-8")


def test_compare_reports_pairs_cases_and_refuses_mismatches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    report = tmp_path / "a.json"
    args = ["eval-benchmark", "--split", "dev", "--systems", "F", "--resamples", "0"]
    args += ["--benchmark-version", "v1", "--no-models", "--dataset", str(DATASET)]
    assert cli.main([*args, "--out", str(report)]) == 0

    out = tmp_path / "diff.json"
    assert cli.main(["compare-reports", str(report), str(report), "--out", str(out)]) == 0
    assert "acc +0.000" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["pooled"]["accuracy"]["estimate"] == 0.0

    data = json.loads(report.read_text(encoding="utf-8"))
    data["systems"][0]["cases"] = data["systems"][0]["cases"][1:]
    fewer = tmp_path / "fewer.json"
    fewer.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["compare-reports", str(report), str(fewer)]) == 2

    data = json.loads(report.read_text(encoding="utf-8"))
    case = data["systems"][0]["cases"][0]
    case["expected"] = "UNCERTAIN" if case["expected"] != "UNCERTAIN" else "SATISFIED"
    relabelled = tmp_path / "relabelled.json"
    relabelled.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["compare-reports", str(report), str(relabelled)]) == 2
    assert "gold labels differ" in capsys.readouterr().err
