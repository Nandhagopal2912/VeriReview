from pathlib import Path

from verireview.dataset import load_fixture
from verireview.verification import mvp_pipeline

FIXTURES = Path(__file__).resolve().parents[3] / "dataset" / "fixtures"


def explain(case_id: str) -> str:
    return mvp_pipeline().run(load_fixture(FIXTURES / case_id).case).explanation


def test_partial_shows_satisfied_and_missing_requirements() -> None:
    text = explain("api-002-validation-without-400")

    assert "✓ R1 (validation):" in text
    assert "✗ R2 (api_behavior):" in text
    assert "Result:\nPARTIALLY_SATISFIED" in text


def test_evidence_locations_cite_commits() -> None:
    case = load_fixture(FIXTURES / "validation-001-none-check").case
    text = mvp_pipeline().run(case).explanation

    assert f"@ {case.window.end_commit_sha[:7]} (after)" in text
    assert f"@ {case.window.start_commit_sha[:7]} (before)" in text


def test_uncertain_requirements_are_marked() -> None:
    text = explain("naming-005-vague-request")

    assert "? R1 (naming):" in text
    assert "a human should confirm" in text
