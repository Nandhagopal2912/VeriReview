from pathlib import Path

import pytest

from verireview.contracts import Verdict
from verireview.dataset import iter_fixtures
from verireview.evaluation import dataset_hash
from verireview.evaluation.baselines import (
    roc_auc,
    run_baseline,
    tune_threshold,
    tune_threshold_youden,
)
from verireview.semantic import LexicalScorer, TfidfScorer

S, N, P, U = (
    Verdict.SATISFIED,
    Verdict.NOT_SATISFIED,
    Verdict.PARTIALLY_SATISFIED,
    Verdict.UNCERTAIN,
)
DATASET = Path(__file__).resolve().parents[3] / "dataset"


def test_threshold_maximises_accuracy_and_prefers_the_conservative_tie() -> None:
    scores = [0.9, 0.8, 0.3, 0.2]
    gold = [S, S, N, N]

    t = tune_threshold(scores, gold)

    assert 0.3 < t <= 0.8  # separates perfectly; highest such threshold chosen
    assert t == pytest.approx(0.55)


def test_threshold_collapses_to_majority_when_scores_carry_no_signal() -> None:
    # Invalid resolutions score higher: the best achievable is "always NOT_SATISFIED".
    t = tune_threshold([0.9, 0.8, 0.2], [N, N, S])

    assert all(score < t for score in [0.9, 0.8, 0.2])


def test_roc_auc() -> None:
    assert roc_auc([0.9, 0.8, 0.2, 0.1], [S, S, N, P]) == 1.0
    assert roc_auc([0.1, 0.2, 0.8, 0.9], [S, S, N, N]) == 0.0
    assert roc_auc([0.5, 0.5], [S, N]) == 0.5
    assert roc_auc([0.5, 0.7], [S, U]) is None  # no invalid case; UNCERTAIN ignored


def test_youden_threshold_balances_the_two_error_rates() -> None:
    t = tune_threshold_youden([0.9, 0.6, 0.4, 0.1], [S, S, N, N])

    assert 0.4 < t < 0.6


def test_harness_uses_the_same_evaluation_as_the_rules() -> None:
    dev = list(iter_fixtures(DATASET / "fixtures"))
    held = list(iter_fixtures(DATASET / "heldout_fixtures"))

    result = run_baseline(
        TfidfScorer(), dev, held, DATASET / "fixtures", DATASET / "heldout_fixtures"
    )

    assert result.dev.dataset_hash == dataset_hash(DATASET / "fixtures")
    assert result.heldout.pipeline_version == "baseline-tfidf-1"
    assert result.dev.metrics.n == len(dev) and result.heldout.metrics.n == len(held)
    assert set(result.scores) == {f.meta.case_id for f in dev + held}
    assert result.auc_dev is not None and 0.0 <= result.auc_dev <= 1.0


def test_harness_is_deterministic() -> None:
    dev = list(iter_fixtures(DATASET / "fixtures"))
    held = list(iter_fixtures(DATASET / "heldout_fixtures"))

    a = run_baseline(LexicalScorer(), dev, held, DATASET / "fixtures", DATASET / "heldout_fixtures")
    b = run_baseline(LexicalScorer(), dev, held, DATASET / "fixtures", DATASET / "heldout_fixtures")

    assert a == b
