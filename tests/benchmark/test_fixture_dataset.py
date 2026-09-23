"""Integrity of the dev fixture set (roadmap Phase 2 targets). Fails if the dataset degrades."""

from collections import Counter
from pathlib import Path

import pytest

from verireview.contracts import RequirementCategory, Verdict
from verireview.dataset import Fixture, HardCase, iter_fixtures

ROOT = Path(__file__).resolve().parents[2] / "dataset" / "fixtures"
FIXTURES = list(iter_fixtures(ROOT))
MVP_CATEGORIES = set(RequirementCategory) - {RequirementCategory.OTHER}


def test_at_least_25_fixtures() -> None:
    assert len(FIXTURES) >= 25


def test_every_mvp_category_has_at_least_5_cases() -> None:
    counts = Counter(f.meta.category for f in FIXTURES)
    assert {c: counts[c] for c in MVP_CATEGORIES if counts[c] < 5} == {}


def test_every_verdict_is_represented() -> None:
    assert {f.meta.expected_verdict for f in FIXTURES} == set(Verdict)


def test_plan_hard_cases_are_covered() -> None:
    present = {f.meta.hard_case for f in FIXTURES}
    required = {
        HardCase.LEXICAL_FALSE_POSITIVE,
        HardCase.PARTIAL,
        HardCase.UNRELATED_CHANGE,
        HardCase.PRE_EXISTING,
    }
    assert required <= present


def test_case_ids_are_unique() -> None:
    ids = [f.case.case_id for f in FIXTURES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.meta.case_id)
def test_partial_cases_have_several_requirements(fixture: Fixture) -> None:
    if fixture.meta.expected_verdict == Verdict.PARTIALLY_SATISFIED:
        assert len(fixture.meta.requirements) >= 2


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.meta.case_id)
def test_fixture_code_is_valid_python(fixture: Fixture) -> None:
    for code in (
        fixture.case.before_code,
        fixture.case.after_code,
        *fixture.case.test_files.values(),
    ):
        assert code is not None
        compile(code, fixture.meta.case_id, "exec")


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.meta.case_id)
def test_requirement_ids_are_unique_within_case(fixture: Fixture) -> None:
    ids = [r.id for r in fixture.meta.requirements]
    assert len(ids) == len(set(ids))
