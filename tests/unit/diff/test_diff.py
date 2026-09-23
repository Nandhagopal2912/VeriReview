import pytest

from verireview.diff import (
    Change,
    DiffParseError,
    changes,
    line_mapping,
    parse_unified_diff,
    similarity,
)
from verireview.ingestion import make_unified_diff

BEFORE = "def f(x):\n    a = 1\n    return x\n"
AFTER = "def f(x):\n    if x is None:\n        raise ValueError\n    a = 1\n    return x\n"


def test_parses_files_hunks_and_line_numbers() -> None:
    (file_diff,) = parse_unified_diff(make_unified_diff(BEFORE, AFTER, "m.py", "m.py"))

    assert (file_diff.before_path, file_diff.after_path) == ("m.py", "m.py")
    (hunk,) = file_diff.hunks
    assert [(line.number, line.text) for line in hunk.added] == [
        (2, "    if x is None:"),
        (3, "        raise ValueError"),
    ]
    assert hunk.removed == ()
    assert file_diff.added_lines == {2, 3}
    assert file_diff.removed_lines == frozenset()


def test_removed_lines_use_before_numbers() -> None:
    (file_diff,) = parse_unified_diff(make_unified_diff(AFTER, BEFORE, "m.py", "m.py"))

    assert file_diff.removed_lines == {2, 3}


def test_added_and_deleted_files_have_none_paths() -> None:
    (added,) = parse_unified_diff(make_unified_diff(None, "x = 1\n", "n.py", "n.py"))
    (deleted,) = parse_unified_diff(make_unified_diff("x = 1\n", None, "n.py", "n.py"))

    assert (added.before_path, added.after_path) == (None, "n.py")
    assert (deleted.before_path, deleted.after_path) == ("n.py", None)


def test_missing_final_newline_marker_is_handled() -> None:
    (file_diff,) = parse_unified_diff(make_unified_diff("x = 1", "x = 2", "m.py", "m.py"))

    assert [line.text for line in file_diff.hunks[0].added] == ["x = 2"]


def test_empty_diff_is_empty_list() -> None:
    assert parse_unified_diff("") == []


def test_malformed_diff_raises() -> None:
    with pytest.raises(DiffParseError):
        parse_unified_diff("--- a/x\n+++ b/x\n@@ -1,3 +1,3 @@\n-only one line\n")


def test_changes_and_mapping_agree() -> None:
    assert changes(BEFORE, AFTER) == [Change(1, 1, 1, 3)]
    mapping = line_mapping(BEFORE, AFTER)
    assert mapping[1] == 1 and mapping[2] == 4 and mapping[3] == 5


def test_similarity_bounds() -> None:
    assert similarity([], []) == 1.0
    assert similarity(["a", "b"], ["a", "b"]) == 1.0
    assert similarity(["a"], ["b"]) == 0.0
    assert 0 < similarity(["a", "b", "c"], ["a", "x", "c"]) < 1
