import pytest

from helpers.cases import REQUIREMENT, make_case
from verireview.contracts import ReviewCase
from verireview.evidence.locality import (
    NEAR_TARGET_RADIUS,
    Change,
    change_locality_evidence,
    changes,
)

BEFORE = "\n".join(f"line{i}" for i in range(1, 41)) + "\n"  # 40 lines


def facts(case: ReviewCase) -> dict[str, bool | None]:
    return {e.kind: e.passed for e in change_locality_evidence(case, REQUIREMENT)}


def edit(line: int, text: str = "changed") -> str:
    lines = BEFORE.split("\n")
    lines[line - 1] = text
    return "\n".join(lines)


def test_change_on_commented_line_is_near() -> None:
    assert facts(make_case(BEFORE, edit(5))) == {
        "file_changed": True,
        "change_near_target": True,
        "tests_changed": False,
    }


def test_change_just_outside_radius_is_not_near() -> None:
    far = 5 + NEAR_TARGET_RADIUS + 1

    assert facts(make_case(BEFORE, edit(far)))["change_near_target"] is False


def test_change_at_radius_edge_is_near() -> None:
    assert facts(make_case(BEFORE, edit(5 + NEAR_TARGET_RADIUS)))["change_near_target"] is True


def test_insertion_right_after_commented_line_is_near() -> None:
    after = BEFORE.replace("line5\n", "line5\ninserted\n")

    assert facts(make_case(BEFORE, after))["change_near_target"] is True


def test_no_change_at_all() -> None:
    assert facts(make_case(BEFORE, BEFORE)) == {
        "file_changed": False,
        "change_near_target": False,
        "tests_changed": False,
    }


def test_changed_tests_are_reported_with_location() -> None:
    evidence = change_locality_evidence(
        make_case(BEFORE, BEFORE, tests={"tests/test_m.py": "def test_x():\n    pass\n"}),
        REQUIREMENT,
    )
    tests = next(e for e in evidence if e.kind == "tests_changed")

    assert tests.passed is True
    assert tests.location is not None and tests.location.file == "tests/test_m.py"


@pytest.mark.parametrize(
    ("before", "after", "anchor"), [(None, "x", 1), ("x", None, 1), ("x", "y", None)]
)
def test_missing_inputs_give_one_neutral_item(
    before: str | None, after: str | None, anchor: int | None
) -> None:
    (only,) = change_locality_evidence(make_case(before, after, anchor), REQUIREMENT)

    assert (only.kind, only.passed) == ("code_unavailable", None)


def test_every_item_is_located_or_explained() -> None:
    for case in (
        make_case(BEFORE, edit(5)),
        make_case(BEFORE, BEFORE),
        make_case(BEFORE, edit(30)),
    ):
        for item in change_locality_evidence(case, REQUIREMENT):
            assert (item.location is None) != (item.no_location_reason is None)


def test_changes_reports_regions() -> None:
    assert changes("a\nb\nc", "a\nB\nc") == [Change(1, 2, 1, 2)]


def test_touches_handles_insertions_and_ranges() -> None:
    insertion = Change(4, 4, 4, 5)  # inserted between before-lines 4 and 5
    replacement = Change(9, 12, 9, 12)  # before-lines 10..12

    assert insertion.touches(5, 8) and insertion.touches(1, 4)
    assert not insertion.touches(6, 9)
    assert replacement.touches(12, 20) and replacement.touches(1, 10)
    assert not replacement.touches(13, 20)
