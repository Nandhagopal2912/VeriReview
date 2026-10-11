"""Re-scoring a recorded run against current labels (no verifier run)."""

from verireview.contracts import Confidence, Verdict
from verireview.evaluation.benchmark import CaseRecord
from verireview.evaluation.rescore import rescore

S, N, U = Verdict.SATISFIED, Verdict.NOT_SATISFIED, Verdict.UNCERTAIN


def record(
    case_id: str, expected: Verdict, predicted: Verdict, source: str = "real_world"
) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        source=source,
        category="other",
        hard_case=None,
        expected=expected,
        predicted=predicted,
        confidence=Confidence.MEDIUM,
    )


RECORDS = [
    record("c1", S, S, source="controlled"),  # authored case: never relabelled
    record("rw-same", S, S),
    record("rw-lenient", S, S),  # the model label and the verifier agreed; the human says NOT
    record("rw-dropped", S, U),  # excluded by the current labels
    record("rw-unlabelled", N, N),  # no current label: keeps the recorded one
]
CURRENT = {"rw-same": S, "rw-lenient": N, "rw-dropped": None, "rw-new": S}


def test_recorded_slice_is_the_run_as_it_was_scored() -> None:
    pooled, real_world, *_ = rescore(RECORDS, CURRENT, resamples=0)

    assert pooled.recorded.n == 5 and pooled.recorded.metrics.accuracy == 0.8
    assert real_world.recorded.n == 4


def test_current_labels_reveal_a_false_acceptance_the_old_labels_hid() -> None:
    pooled, real_world, excluded, unseen, changes = rescore(RECORDS, CURRENT, resamples=0)

    old, new = real_world.same_cases_recorded_labels, real_world.same_cases_current_labels
    assert old.n == new.n == 3  # the same cases on both sides
    assert old.metrics.false_acceptance_rate == 0.0  # one bad case (rw-unlabelled), rejected
    assert new.metrics.false_acceptance_rate == 0.5  # rw-lenient was accepted
    assert pooled.same_cases_current_labels.n == 4  # the controlled case is still there
    assert excluded == ["rw-dropped"]
    assert unseen == ["rw-new"]  # included now, never run: listed, not scored
    assert [(c.case_id, c.recorded, c.current, c.predicted) for c in changes] == [
        ("rw-lenient", S, N, S)
    ]


def test_unchanged_labels_change_nothing() -> None:
    current = {r.case_id: r.expected for r in RECORDS if r.source == "real_world"}
    pooled, real_world, excluded, unseen, changes = rescore(RECORDS, current, resamples=0)

    assert pooled.same_cases_current_labels == pooled.recorded
    assert real_world.same_cases_current_labels == real_world.recorded
    assert (excluded, unseen, changes) == ([], [], [])
