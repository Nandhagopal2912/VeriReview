from pathlib import Path

import pytest

from verireview.contracts import Confidence, Verdict
from verireview.dataset import Fixture, iter_fixtures
from verireview.verification import (
    DEFAULT_PIPELINE,
    PIPELINES,
    STRUCTURAL_VERSION,
    get_pipeline,
    structural_pipeline,
)
from verireview.verification.structural import STRUCTURAL_NOTE

FIXTURES = {
    f.meta.case_id: f
    for f in iter_fixtures(Path(__file__).resolve().parents[3] / "dataset" / "fixtures")
}


def verdict(case_id: str) -> tuple[Verdict, Confidence]:
    result = structural_pipeline().run(FIXTURES[case_id].case)
    return result.verdict, result.confidence


def test_comment_only_fixes_are_no_longer_accepted() -> None:
    # Phase 2 accepted both; a comment/TODO that mentions the fix is not a code change.
    assert verdict("naming-003-comment-mentions-name") == (Verdict.NOT_SATISFIED, Confidence.MEDIUM)
    assert verdict("api-004-todo-comment") == (Verdict.NOT_SATISFIED, Confidence.MEDIUM)


def test_real_fix_in_target_is_accepted_with_low_confidence() -> None:
    assert verdict("validation-001-none-check") == (Verdict.SATISFIED, Confidence.LOW)


def test_test_only_change_is_accepted() -> None:
    assert verdict("testing-001-empty-username-test") == (Verdict.SATISFIED, Confidence.LOW)


@pytest.mark.parametrize("fixture", list(FIXTURES.values()), ids=lambda f: f.meta.case_id)
def test_every_fixture_yields_a_valid_cited_result(fixture: Fixture) -> None:
    result = structural_pipeline().run(fixture.case)

    assert result.pipeline_version == STRUCTURAL_VERSION
    assert result.confidence != Confidence.HIGH
    for e in result.evidence:
        assert f"[{e.id}] {e.detail}" in result.explanation
    assert STRUCTURAL_NOTE in result.explanation


def test_registry_default_is_latest_phase() -> None:
    assert DEFAULT_PIPELINE == "phase3-structure"
    assert set(PIPELINES) == {"phase2-locality", "phase3-structure"}
    assert get_pipeline().version == STRUCTURAL_VERSION
