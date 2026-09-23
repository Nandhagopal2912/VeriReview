import pytest

from verireview.contracts import Verdict
from verireview.evaluation import compute_metrics
from verireview.evaluation.metrics import false_acceptance_rate, false_blocking_rate

S, P, N, U = (
    Verdict.SATISFIED,
    Verdict.PARTIALLY_SATISFIED,
    Verdict.NOT_SATISFIED,
    Verdict.UNCERTAIN,
)


def test_hand_computed_example() -> None:
    # gold → predicted
    pairs = [(S, S), (S, S), (S, N), (N, N), (N, S), (P, S), (U, U)]

    m = compute_metrics(pairs)

    assert m.n == 7
    assert m.accuracy == pytest.approx(4 / 7)
    # SATISFIED: tp=2, predicted=4 (S,S,N→S,P→S), support=3
    assert m.per_class[S].precision == pytest.approx(2 / 4)
    assert m.per_class[S].recall == pytest.approx(2 / 3)
    assert m.per_class[S].f1 == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))
    # PARTIAL never predicted and 1 support → all zero
    assert (m.per_class[P].precision, m.per_class[P].recall, m.per_class[P].f1) == (0, 0, 0)
    assert m.confusion[S][N] == 1 and m.confusion[P][S] == 1
    # FAR: invalid = gold N or P = [N→N, N→S, P→S] → 2 of 3 accepted
    assert m.false_acceptance_rate == pytest.approx(2 / 3)
    # FBR: gold S = [S, S, N] → 1 of 3 blocked
    assert m.false_blocking_rate == pytest.approx(1 / 3)


def test_macro_f1_averages_only_classes_present_in_gold() -> None:
    m = compute_metrics([(S, S), (N, N)])

    assert m.macro_f1 == 1.0


def test_perfect_predictions() -> None:
    pairs = [(v, v) for v in Verdict]

    m = compute_metrics(pairs)

    assert m.accuracy == 1.0 and m.macro_f1 == 1.0
    assert m.false_acceptance_rate == 0.0 and m.false_blocking_rate == 0.0


def test_rates_are_none_without_a_denominator() -> None:
    assert false_acceptance_rate([(S, S)]) is None
    assert false_blocking_rate([(N, N)]) is None


def test_uncertain_is_neither_acceptance_nor_blocking() -> None:
    assert false_acceptance_rate([(N, U)]) == 0.0
    assert false_blocking_rate([(S, U)]) == 0.0


def test_empty_input() -> None:
    m = compute_metrics([])

    assert (m.n, m.accuracy, m.macro_f1) == (0, 0.0, 0.0)
