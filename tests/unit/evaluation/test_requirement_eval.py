import pytest

from verireview.contracts import RequirementCategory
from verireview.evaluation.requirements import RequirementExample, evaluate_extraction

C = RequirementCategory


def example(
    eid: str, comment: str, gold: tuple[C, ...], ambiguous: bool | None
) -> RequirementExample:
    return RequirementExample(
        id=eid,
        comment=comment,
        code=None,
        anchor_line=None,
        gold_categories=gold,
        gold_ambiguous=ambiguous,
    )


def test_scores_counts_categories_actionability_and_ambiguity() -> None:
    examples = [
        example("a", "Rename `x` to `y`.", (C.NAMING,), False),  # perfect
        example("b", "Add a test for `f`.", (C.TESTING, C.TESTING), False),  # count wrong
        example("c", "LGTM", (), None),  # nothing requested, correctly
        example("d", "Maybe a better name here?", (C.NAMING,), True),  # ambiguous, caught
    ]

    report = evaluate_extraction(examples, "t", "h")

    assert report.n == 4
    assert report.count_exact == pytest.approx(3 / 4)
    # predicted: naming, testing, naming ; gold: naming, testing×2, naming → 3 matched
    assert report.category_precision == pytest.approx(3 / 3)
    assert report.category_recall == pytest.approx(3 / 4)
    assert report.actionable_accuracy == 1.0
    assert (report.ambiguity_precision, report.ambiguity_recall) == (1.0, 1.0)
    assert report.target_symbol_accuracy is None


def test_ambiguity_rates_undefined_without_positives() -> None:
    report = evaluate_extraction([example("a", "Rename `x` to `y`.", (C.NAMING,), False)], "t", "h")

    assert report.ambiguity_precision is None and report.ambiguity_recall is None
