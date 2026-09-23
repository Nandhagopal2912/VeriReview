"""Phase 9 benchmark integrity. The test-split case sets are frozen: their hashes were pinned
right after they were written, before any verifier ran on them (docs/phase9_benchmark.md)."""

from collections import Counter
from pathlib import Path

import pytest

from verireview.contracts import RequirementCategory, Verdict
from verireview.dataset import Fixture, iter_fixtures
from verireview.evaluation import dataset_hash

BENCHMARK = Path(__file__).resolve().parents[2] / "dataset" / "benchmark"
FROZEN = {
    "controlled": "f1ebeb9fa1dba38f25f245fa0855c1dec80532b94f352bcb2de58b5010671de7",
    "adversarial": "494acdc0edcb4b12df96456e9d3f4cc50de3ae98b660213fd2e855d8d3d6e8a5",
}
CASES = {name: list(iter_fixtures(BENCHMARK / name)) for name in FROZEN}
ALL = [f for fixtures in CASES.values() for f in fixtures]
MVP_CATEGORIES = set(RequirementCategory) - {RequirementCategory.OTHER}


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_frozen_case_sets_are_unchanged(name: str) -> None:
    assert dataset_hash(BENCHMARK / name) == FROZEN[name]


def test_sizes_meet_the_v1_targets() -> None:
    assert len(CASES["controlled"]) >= 60  # + 53 dev fixtures = 113 controlled (target >= 100)
    assert len(CASES["adversarial"]) >= 30


def test_every_category_has_20_test_cases_and_every_verdict_appears() -> None:
    counts = Counter(f.meta.category for f in ALL)
    assert {c: counts[c] for c in MVP_CATEGORIES if counts[c] < 20} == {}
    assert {f.meta.expected_verdict for f in ALL} == set(Verdict)


def test_case_ids_are_unique_across_the_benchmark() -> None:
    dev = [*iter_fixtures(BENCHMARK.parent / "fixtures")]
    dev += iter_fixtures(BENCHMARK.parent / "heldout_fixtures")
    ids = [f.meta.case_id for f in [*ALL, *dev]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("fixture", ALL, ids=lambda f: f.meta.case_id)
def test_case_is_well_formed(fixture: Fixture) -> None:
    for code in (
        fixture.case.before_code,
        fixture.case.after_code,
        *fixture.case.test_files.values(),
    ):
        assert code is not None
        compile(code, fixture.meta.case_id, "exec")
    if fixture.meta.expected_verdict == Verdict.PARTIALLY_SATISFIED:
        assert len(fixture.meta.requirements) >= 2
    ids = [r.id for r in fixture.meta.requirements]
    assert len(ids) == len(set(ids))
    assert fixture.meta.requirements[0].category == fixture.meta.category
