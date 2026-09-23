"""Phase 7 safety property: instructions planted in PR content never change an outcome.

Every dev and held-out fixture is re-run with prompt injections in the code, tests, thread
replies, commit messages and PR title (`evaluation.injection`). The outcome (verdict, confidence,
per-requirement statuses) must be identical to the outcome without them.
"""

from pathlib import Path

import pytest

from helpers.semantic import fake_encoder
from verireview.dataset import iter_fixtures
from verireview.evaluation.injection import Site, injection_report
from verireview.semantic import LexicalScorer, SimilarityVerifier
from verireview.verification import mvp_pipeline, semantic_pipeline

DATASET = Path(__file__).resolve().parents[2] / "dataset"
ROOTS = ["fixtures", "heldout_fixtures"]


@pytest.mark.parametrize("root", ROOTS)
def test_mvp_outcomes_ignore_injected_instructions(root: str) -> None:
    report = injection_report(mvp_pipeline(), iter_fixtures(DATASET / root))

    assert report.flips == []
    assert all(report.by_site[site] > 0 for site in Site)  # every site was exercised


@pytest.mark.parametrize("root", ROOTS)
def test_semantic_pipeline_outcomes_ignore_injected_instructions(root: str) -> None:
    report = injection_report(semantic_pipeline(fake_encoder), iter_fixtures(DATASET / root))

    assert report.flips == []


def test_the_suite_does_catch_a_verifier_that_reads_comments() -> None:
    """Sanity check of the suite itself: the Phase 6 lexical baseline is fooled."""
    lexical = SimilarityVerifier(LexicalScorer(), threshold=0.174)  # Phase 6 Youden threshold

    report = injection_report(lexical, iter_fixtures(DATASET / "fixtures"))

    assert any(f.site == Site.INJECTION_ONLY for f in report.flips)
