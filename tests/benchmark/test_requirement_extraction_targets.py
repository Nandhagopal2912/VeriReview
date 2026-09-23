"""Roadmap Phase 4 targets as regression tests, on dev fixtures AND the held-out set."""

from pathlib import Path

import pytest

from verireview.dataset import iter_fixtures
from verireview.evaluation.requirements import (
    ExtractionReport,
    evaluate_extraction,
    file_hash,
    fixture_examples,
    heldout_examples,
)

ROOT = Path(__file__).resolve().parents[2] / "dataset"
HELDOUT = ROOT / "requirements" / "heldout.jsonl"
# Written before the extractor existed. Editing it would invalidate the reported blind result,
# so any change must be deliberate: update this hash AND docs/phase4_requirements.md.
HELDOUT_SHA256 = "13fe739965b0fa8300fea5b289a3e9bf70f57f87d2900da3202c0b41eafd973c"


@pytest.fixture(scope="module")
def dev() -> ExtractionReport:
    return evaluate_extraction(fixture_examples(list(iter_fixtures(ROOT / "fixtures"))), "dev", "-")


@pytest.fixture(scope="module")
def heldout() -> ExtractionReport:
    return evaluate_extraction(heldout_examples(HELDOUT), "held-out", file_hash(HELDOUT))


def test_heldout_set_is_unchanged() -> None:
    assert file_hash(HELDOUT) == HELDOUT_SHA256


@pytest.mark.parametrize("name", ["dev", "heldout"])
def test_count_exact_at_least_80_percent(name: str, request: pytest.FixtureRequest) -> None:
    report: ExtractionReport = request.getfixturevalue(name)
    assert report.count_exact >= 0.80


@pytest.mark.parametrize("name", ["dev", "heldout"])
def test_category_f1_at_least_85_percent(name: str, request: pytest.FixtureRequest) -> None:
    report: ExtractionReport = request.getfixturevalue(name)
    assert report.category_f1 >= 0.85


def test_target_symbol_found_for_every_fixture(dev: ExtractionReport) -> None:
    assert dev.target_symbol_accuracy == 1.0
