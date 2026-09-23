from pathlib import Path

from helpers.semantic import fake_encoder
from verireview.contracts import Verdict
from verireview.dataset import iter_fixtures
from verireview.evaluation.baselines import run_baseline
from verireview.evaluation.semantic import (
    CaseRelevance,
    SemanticEvidenceReport,
    evaluate_semantic_evidence,
    operating_point,
    youden_threshold,
)
from verireview.semantic import LexicalScorer

DATASET = Path(__file__).resolve().parents[3] / "dataset"


def test_semantic_evidence_report_on_dev() -> None:
    root = DATASET / "fixtures"

    report = evaluate_semantic_evidence("dev", list(iter_fixtures(root)), root, fake_encoder)

    assert report.n == len(report.cases) == 29
    assert report.verdict_changes == 0
    assert report.auc is not None and 0.0 <= report.auc <= 1.0
    no_code = next(c for c in report.cases if c.case_id == "naming-003-comment-mentions-name")
    assert no_code.scores == {} and no_code.case_score == 0.0  # comment-only change


def test_code_view_baseline_is_reported_separately() -> None:
    dev = list(iter_fixtures(DATASET / "fixtures"))
    held = list(iter_fixtures(DATASET / "heldout_fixtures"))

    result = run_baseline(
        LexicalScorer(), dev, held, DATASET / "fixtures", DATASET / "heldout_fixtures", "code"
    )

    assert result.view == "code"
    assert result.dev.pipeline_version == "baseline-lexical-code-1"
    # The comment-only trap scores nothing once comments are removed.
    assert result.scores["naming-003-comment-mentions-name"] == 0.0


def test_operating_point_counts_both_error_kinds() -> None:
    def c(gold: Verdict, score: float) -> CaseRelevance:
        return CaseRelevance(
            case_id=f"{gold}-{score}", gold=gold, mvp=gold, phase7=gold, scores={}, case_score=score
        )

    s, n, u = Verdict.SATISFIED, Verdict.NOT_SATISFIED, Verdict.UNCERTAIN
    cases = [c(s, 0.9), c(s, 0.3), c(n, 0.8), c(n, 0.1), c(u, 0.95)]
    report = SemanticEvidenceReport(
        name="t", dataset_hash="h", model={}, n=5, verdict_changes=0, auc=0.5, cases=cases
    )

    assert operating_point(report, 0.5) == (0.5, 0.5)  # UNCERTAIN is left out
    assert 0.1 < youden_threshold(report) <= 0.9
