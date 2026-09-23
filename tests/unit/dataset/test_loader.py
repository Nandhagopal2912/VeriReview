import json
from pathlib import Path

import pytest

from verireview.contracts import Verdict, WindowFlag
from verireview.dataset import FixtureError, iter_fixtures, load_fixture

META = {
    "case_id": "demo-001",
    "category": "validation",
    "file_path": "app/service.py",
    "target_symbol": "save",
    "comment_line": 2,
    "expected_verdict": "SATISFIED",
    "hard_case": None,
    "rationale": "A check was added before the save.",
    "requirements": [{"id": "R1", "category": "validation", "description": "check x"}],
}
BEFORE = "def save(x):\n    db.insert(x)\n"
AFTER = "def save(x):\n    if x is None:\n        raise ValueError\n    db.insert(x)\n"


def make_fixture(root: Path, **overrides: object) -> Path:
    meta = {**META, **overrides}
    d = root / str(meta["case_id"])
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (d / "comment.txt").write_text("Add a None check for `x`.\n", encoding="utf-8")
    (d / "before.py").write_text(BEFORE, encoding="utf-8")
    (d / "after.py").write_text(AFTER, encoding="utf-8")
    return d


def test_loads_a_review_case(tmp_path: Path) -> None:
    fixture = load_fixture(make_fixture(tmp_path))
    case = fixture.case

    assert case.case_id == "fixture/demo-001"
    assert case.thread.root.body == "Add a None check for `x`."
    assert case.anchor_line == 2
    assert case.thread.diff_hunk.splitlines()[-1] == "     db.insert(x)"
    assert "+    if x is None:" in case.unified_diff
    assert [f.path for f in case.changed_files] == ["app/service.py"]
    assert fixture.meta.expected_verdict == Verdict.SATISFIED
    assert fixture.gold_requirement.source == "manual"


def test_loading_is_deterministic(tmp_path: Path) -> None:
    d = make_fixture(tmp_path)

    assert load_fixture(d).case == load_fixture(d).case


def test_unchanged_code_has_no_subsequent_commits(tmp_path: Path) -> None:
    d = make_fixture(tmp_path)
    (d / "after.py").write_text(BEFORE, encoding="utf-8")

    case = load_fixture(d).case

    assert case.window.subsequent_commits == []
    assert case.window.end_commit_sha == case.window.start_commit_sha
    assert WindowFlag.NO_SUBSEQUENT_COMMITS in case.window.flags
    assert case.unified_diff == ""


def test_test_files_contain_only_changed_tests(tmp_path: Path) -> None:
    d = make_fixture(tmp_path)
    for folder, content in (("tests_before", "old\n"), ("tests_after", "new\n")):
        (d / folder / "tests").mkdir(parents=True)
        (d / folder / "tests" / "test_changed.py").write_text(content, encoding="utf-8")
        (d / folder / "tests" / "test_same.py").write_text("same\n", encoding="utf-8")

    case = load_fixture(d).case

    assert case.test_files == {"tests/test_changed.py": "new\n"}
    assert [(f.path, f.status, f.is_test) for f in case.changed_files if f.is_test] == [
        ("tests/test_changed.py", "modified", True)
    ]


def test_case_id_must_match_directory(tmp_path: Path) -> None:
    d = make_fixture(tmp_path)
    d.rename(tmp_path / "other-name")

    with pytest.raises(FixtureError, match="directory name"):
        load_fixture(tmp_path / "other-name")


def test_comment_line_must_point_at_code(tmp_path: Path) -> None:
    with pytest.raises(FixtureError, match="not a code line"):
        load_fixture(make_fixture(tmp_path, comment_line=3))


def test_missing_file_is_reported(tmp_path: Path) -> None:
    d = make_fixture(tmp_path)
    (d / "after.py").unlink()

    with pytest.raises(FixtureError, match="Missing fixture file"):
        load_fixture(d)


def test_unknown_meta_fields_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_fixture(make_fixture(tmp_path, surprise=True))


def test_iter_fixtures_is_sorted(tmp_path: Path) -> None:
    make_fixture(tmp_path, case_id="b-case")
    make_fixture(tmp_path, case_id="a-case")

    assert [f.meta.case_id for f in iter_fixtures(tmp_path)] == ["a-case", "b-case"]
