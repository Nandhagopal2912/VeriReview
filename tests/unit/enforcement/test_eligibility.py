"""The enforcement gate: exact upper bounds, the per-category rule, and the shipped file."""

import json
from pathlib import Path

import pytest

from verireview.contracts import RequirementCategory, Verdict
from verireview.enforcement import eligibility
from verireview.enforcement.eligibility import compute, load_shipped, upper_bound

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "experiments" / "phase10_1_test.json"


@pytest.mark.parametrize(
    ("errors", "n", "expected"),
    [
        (0, 10, 0.258866),
        (0, 59, 0.049508),
        (0, 60, 0.048703),
        (3, 10, 0.606624),
        (5, 100, 0.102253),
    ],
)
def test_clopper_pearson_upper_bound(errors: int, n: int, expected: float) -> None:
    assert upper_bound(errors, n) == pytest.approx(expected, abs=1e-6)


def test_bound_agrees_with_scipy_where_available() -> None:
    stats = pytest.importorskip("scipy.stats")
    for errors, n in [(0, 1), (1, 7), (4, 30), (12, 40), (0, 200)]:
        assert upper_bound(errors, n) == pytest.approx(stats.beta.ppf(0.95, errors + 1, n - errors))


def test_degenerate_counts_are_never_reassuring() -> None:
    assert upper_bound(0, 0) == 1.0  # no evidence at all
    assert upper_bound(5, 5) == 1.0


def report(path: Path, cases: list[dict], split: str = "test") -> Path:  # type: ignore[type-arg]
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    data["split"] = split
    system = next(s for s in data["systems"] if s["system"] == "F")
    system["cases"] = cases
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def record(i: int, category: str, expected: Verdict, predicted: Verdict) -> dict:  # type: ignore[type-arg]
    return {
        "case_id": f"c{i}",
        "source": "controlled",
        "category": category,
        "hard_case": None,
        "expected": expected.value,
        "predicted": predicted.value,
        "confidence": "MEDIUM",
    }


def clean_category(category: str, n: int) -> list[dict]:  # type: ignore[type-arg]
    bad = [record(i, category, Verdict.NOT_SATISFIED, Verdict.NOT_SATISFIED) for i in range(n)]
    good = [record(n + i, category, Verdict.SATISFIED, Verdict.SATISFIED) for i in range(n)]
    return bad + good


def test_a_category_needs_59_clean_cases_per_class(tmp_path: Path) -> None:
    # 0/59 → upper bound 0.0495; 0/58 → 0.0503.
    enough = compute(report(tmp_path / "a.json", clean_category("naming", 59)))
    too_few = compute(report(tmp_path / "b.json", clean_category("naming", 58)))

    assert enough.eligible_categories() == frozenset({RequirementCategory.NAMING})
    assert too_few.eligible_categories() == frozenset()


def test_one_false_acceptance_in_sixty_is_not_enough(tmp_path: Path) -> None:
    cases = clean_category("naming", 60)
    cases[0]["predicted"] = Verdict.SATISFIED.value

    assert compute(report(tmp_path / "a.json", cases)).eligible_categories() == frozenset()


def test_false_blocking_is_gated_too(tmp_path: Path) -> None:
    cases = clean_category("naming", 60)
    cases[-1]["predicted"] = Verdict.NOT_SATISFIED.value  # a good resolution called not satisfied

    [naming] = [
        c
        for c in compute(report(tmp_path / "a.json", cases)).categories
        if c.category == RequirementCategory.NAMING
    ]
    assert not naming.eligible and "false-blocking" in naming.reason


def test_only_a_frozen_test_run_counts(tmp_path: Path) -> None:
    dev = compute(report(tmp_path / "a.json", clean_category("naming", 100), split="dev"))

    assert dev.eligible_categories() == frozenset()
    assert "frozen" in dev.categories[0].reason


def test_shipped_file_admits_no_category_today() -> None:
    """Phase 12 pin: on the v2 test evidence no category may be enforced."""
    shipped = load_shipped()

    assert shipped.eligible_categories() == frozenset()
    assert (shipped.split, shipped.manifest_version, shipped.threshold) == ("test", "v2", 0.05)


def test_shipped_file_is_exactly_what_the_recorded_run_gives() -> None:
    """A hand edit of eligibility.json (e.g. flipping `eligible`) is caught here."""
    if not SOURCE.is_file():  # pragma: no cover - the report is committed
        pytest.skip("recorded report missing")
    recomputed = compute(SOURCE, "F")

    assert load_shipped() == recomputed.model_copy(
        update={"source_report": load_shipped().source_report}
    )


def test_missing_shipped_file_means_nothing_is_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eligibility, "SHIPPED", "does-not-exist.json")

    assert eligibility.eligible_categories() == frozenset()
