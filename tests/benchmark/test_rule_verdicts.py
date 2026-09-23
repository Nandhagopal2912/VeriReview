"""Phase 5 regression guards on verdicts (dev fixtures + blind held-out fixtures)."""

from pathlib import Path

import pytest

from verireview.dataset import iter_fixtures
from verireview.evaluation import EvaluationReport, dataset_hash, evaluate
from verireview.verification import rules_pipeline

DATASET = Path(__file__).resolve().parents[2] / "dataset"
HELDOUT = DATASET / "heldout_fixtures"
# Written after the Phase 5 rules were frozen and run once (docs/phase5_rules.md).
HELDOUT_SHA256 = "d5a64d31c46ef7bbf586d73c0ff1cf93a6a76f606cdd3f485b63a03cb36ac0ae"


def run(root: Path, gold: bool) -> EvaluationReport:
    return evaluate(rules_pipeline(), list(iter_fixtures(root)), root, gold_requirements=gold)


@pytest.mark.parametrize("gold", [False, True], ids=["extracted", "gold"])
def test_dev_fixtures_stay_correct(gold: bool) -> None:
    report = run(DATASET / "fixtures", gold)

    wrong = [c.case_id for c in report.cases if not c.correct]
    assert wrong == []


def test_heldout_fixtures_are_unchanged() -> None:
    assert dataset_hash(HELDOUT) == HELDOUT_SHA256


@pytest.mark.parametrize("gold", [False, True], ids=["extracted", "gold"])
def test_heldout_never_accepts_an_invalid_resolution(gold: bool) -> None:
    """Safety property: rule changes may block more, but must never accept a bad fix."""
    report = run(HELDOUT, gold)

    assert report.metrics.false_acceptance_rate == 0.0
