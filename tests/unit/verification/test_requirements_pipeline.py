from pathlib import Path

import pytest

from verireview.contracts import Confidence, Verdict
from verireview.dataset import Fixture, iter_fixtures
from verireview.verification import (
    DEFAULT_PIPELINE,
    PIPELINES,
    REQUIREMENTS_VERSION,
    get_pipeline,
    requirements_pipeline,
)

FIXTURES = {
    f.meta.case_id: f
    for f in iter_fixtures(Path(__file__).resolve().parents[3] / "dataset" / "fixtures")
}


@pytest.mark.parametrize(
    "case_id",
    ["naming-005-vague-request", "errors-005-question-only", "api-005-idempotency"],
)
def test_ambiguous_requests_go_to_uncertain(case_id: str) -> None:
    result = requirements_pipeline().run(FIXTURES[case_id].case)

    assert (result.verdict, result.confidence) == (Verdict.UNCERTAIN, Confidence.LOW)
    assert "a human should confirm what was asked" in result.explanation
    assert all(s.status == Verdict.UNCERTAIN for s in result.per_requirement)


def test_clear_requests_are_not_gated() -> None:
    result = requirements_pipeline().run(FIXTURES["validation-001-none-check"].case)

    assert result.verdict == Verdict.SATISFIED


def test_multiple_requirements_each_get_a_status() -> None:
    result = requirements_pipeline().run(FIXTURES["api-002-validation-without-400"].case)

    assert [s.requirement_id for s in result.per_requirement] == ["R1", "R2"]
    assert "Requirements:" in result.explanation


@pytest.mark.parametrize("fixture", list(FIXTURES.values()), ids=lambda f: f.meta.case_id)
def test_every_fixture_yields_a_valid_cited_result(fixture: Fixture) -> None:
    result = requirements_pipeline().run(fixture.case)

    assert result.pipeline_version == REQUIREMENTS_VERSION
    for e in result.evidence:
        assert f"[{e.id}] {e.detail}" in result.explanation


def test_default_pipeline_is_phase4() -> None:
    assert DEFAULT_PIPELINE == "phase4-requirements"
    assert set(PIPELINES) == {"phase2-locality", "phase3-structure", "phase4-requirements"}
    assert get_pipeline().version == REQUIREMENTS_VERSION
