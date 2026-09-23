import pytest
from pydantic import ValidationError

from verireview.benchmark import (
    AdjudicationFile,
    AnnotationFile,
    CaseAnnotation,
    PendingAdjudicationError,
    Status,
    agreement,
    build_gold,
    cohen_kappa,
    derive_verdict,
)
from verireview.contracts import Verdict

S, N, U = Status.SATISFIED, Status.NOT_SATISFIED, Status.UNCERTAIN


def label(case_id: str, *statuses: Status, ambiguous: bool = False, **kw: object) -> CaseAnnotation:
    return CaseAnnotation.model_validate(
        {
            "case_id": case_id,
            "include": True,
            "requirements": [
                {"category": "validation", "description": f"requirement {i}", "status": s}
                for i, s in enumerate(statuses, start=1)
            ],
            "ambiguous": ambiguous,
            **kw,
        }
    )


def excluded(case_id: str, reason: str = "no_requirement") -> CaseAnnotation:
    return CaseAnnotation(case_id=case_id, include=False, exclusion_reason=reason)  # type: ignore[arg-type]


def file(annotator: str, *labels: CaseAnnotation) -> AnnotationFile:
    return AnnotationFile(
        annotator=annotator, batch="b", sheet_version="v", annotations=list(labels)
    )


# ---------------------------------------------------------------- labels


@pytest.mark.parametrize(
    ("statuses", "ambiguous", "expected"),
    [
        ([S], False, Verdict.SATISFIED),
        ([S, S], False, Verdict.SATISFIED),
        ([S, N], False, Verdict.PARTIALLY_SATISFIED),
        ([S, N, U], False, Verdict.PARTIALLY_SATISFIED),
        ([N], False, Verdict.NOT_SATISFIED),
        ([N, U], False, Verdict.NOT_SATISFIED),
        ([S, U], False, Verdict.UNCERTAIN),
        ([S], True, Verdict.UNCERTAIN),
    ],
)
def test_verdict_follows_the_guide(
    statuses: list[Status], ambiguous: bool, expected: Verdict
) -> None:
    assert derive_verdict(statuses, ambiguous) == expected
    assert label("c", *statuses, ambiguous=ambiguous).verdict == expected


def test_a_contradictory_verdict_is_rejected() -> None:
    with pytest.raises(ValidationError, match="contradicts"):
        label("c", S, verdict="NOT_SATISFIED")


def test_inclusion_rules() -> None:
    with pytest.raises(ValidationError, match="exclusion_reason"):
        CaseAnnotation(case_id="c", include=False)
    with pytest.raises(ValidationError, match="at least one requirement"):
        CaseAnnotation(case_id="c", include=True)
    assert excluded("c").verdict is None


def test_a_case_cannot_be_annotated_twice() -> None:
    with pytest.raises(ValidationError, match="twice"):
        file("a", label("c", S), label("c", N))


# ---------------------------------------------------------------- kappa


def test_cohen_kappa_textbook_example() -> None:
    # 50 items: both yes 20, both no 15, A yes/B no 5, A no/B yes 10 -> po 0.7, pe 0.5, kappa 0.4
    a = ["y"] * 20 + ["n"] * 15 + ["y"] * 5 + ["n"] * 10
    b = ["y"] * 20 + ["n"] * 15 + ["n"] * 5 + ["y"] * 10

    k = cohen_kappa(a, b)

    assert k.observed == pytest.approx(0.7)
    assert k.kappa == pytest.approx(0.4)


def test_cohen_kappa_edge_cases() -> None:
    assert cohen_kappa(["x", "y"], ["x", "y"]).kappa == pytest.approx(1.0)
    assert cohen_kappa(["x", "x"], ["x", "x"]).kappa is None  # chance agreement 1: undefined
    assert cohen_kappa([], []).n == 0
    with pytest.raises(ValueError, match="length"):
        cohen_kappa(["x"], [])


# ---------------------------------------------------------------- agreement and gold

A = file("ann-a", label("c1", S), label("c2", N), label("c3", S, N), excluded("c4"), label("c5", S))
B = file(
    "ann-b",
    label("c1", S),
    label("c2", S),
    label("c3", S, N, N),
    excluded("c4", "bot_or_automated"),
    excluded("c5"),
)


def test_agreement_report() -> None:
    report = agreement(A, B)

    assert report.common == 5
    assert {d.case_id: d.fields for d in report.disagreements} == {
        "c2": ["verdict"],
        "c3": ["requirement_count"],
        "c5": ["include"],
    }
    assert report.verdict.n == 3  # c1, c2, c3 are included by both
    assert report.verdict.observed == pytest.approx(2 / 3)
    assert report.binary.n == 3
    assert report.by_category["validation"].n == 3


def test_gold_needs_every_disagreement_adjudicated() -> None:
    with pytest.raises(PendingAdjudicationError, match="c2"):
        build_gold(A, B)


def test_gold_from_agreement_and_adjudication() -> None:
    custom = label("c3", S, N, U).model_dump(mode="json")
    adjudication = AdjudicationFile.model_validate(
        {
            "adjudicator": "judge",
            "decisions": [
                {"case_id": "c2", "chosen": "b", "reason": "the check is there"},
                {
                    "case_id": "c3",
                    "chosen": "custom",
                    "label": custom,
                    "reason": "third req unclear",
                },
                {"case_id": "c5", "chosen": "a", "reason": "a real requirement"},
            ],
        }
    )

    gold = build_gold(A, B, adjudication)

    assert set(gold) == {"c1", "c2", "c3", "c4", "c5"}
    assert gold["c1"].agreed and gold["c4"].agreed and not gold["c4"].label.include
    assert gold["c2"].label.verdict == Verdict.SATISFIED and gold["c2"].adjudicator == "judge"
    assert gold["c3"].label.verdict == Verdict.PARTIALLY_SATISFIED
    assert gold["c5"].label.include and gold["c5"].adjudication_reason == "a real requirement"
