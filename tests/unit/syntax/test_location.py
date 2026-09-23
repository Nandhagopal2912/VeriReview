"""Code location resolution (plan §9, roadmap Phase 3 target: 100% on dev fixtures + ≥5 moves)."""

from pathlib import Path
from textwrap import dedent

import pytest

from verireview.dataset import Fixture, iter_fixtures
from verireview.syntax import ResolutionMethod, resolve_target

FIXTURES = list(iter_fixtures(Path(__file__).resolve().parents[3] / "dataset" / "fixtures"))


def code(text: str) -> str:
    return dedent(text).lstrip("\n")


# ---------------------------------------------------------------- dedicated move scenarios


def test_same_function_moved_down_the_file() -> None:
    before = code("""
        def save(x):
            return x
    """)
    after = code("""
        def helper():
            return 1


        def save(x):
            return x
    """)

    r = resolve_target(before, after, 2)

    assert r.method == ResolutionMethod.SAME_NAME
    assert r.after is not None and (r.after.start_line, r.after.end_line) == (5, 6)
    assert r.anchor_after_line == 6
    assert r.moved_to is None


def test_renamed_function_is_matched_by_structure() -> None:
    before = code("""
        def proc(order):
            order.status = "processing"
            return order
    """)
    after = code("""
        def start_processing(order):
            order.status = "processing"
            return order
    """)

    r = resolve_target(before, after, 2)

    assert r.method == ResolutionMethod.RENAMED
    assert r.after is not None and r.after.name == "start_processing"
    assert r.similarity is not None and r.similarity >= 0.6


def test_extracted_helper_plan_section_9() -> None:
    before = code("""
        def save_user(db, username):
            if not username:
                raise ValueError("empty")
            db.insert(username)
    """)
    after = code("""
        def validate_user(username):
            if not username:
                raise ValueError("empty")


        def save_user(db, username):
            validate_user(username)
            db.insert(username)
    """)

    r = resolve_target(before, after, 2)

    assert r.method == ResolutionMethod.SAME_NAME
    assert r.after is not None and r.after.name == "save_user"
    assert r.moved_to is not None and r.moved_to.name == "validate_user"
    assert r.anchor_after_line == 2


def test_renamed_method_keeps_class_qualification() -> None:
    before = code("""
        class Repo:
            def get(self, key):
                value = self.store[key]
                return value
    """)
    after = code("""
        class Repo:
            def fetch(self, key):
                value = self.store[key]
                return value
    """)

    r = resolve_target(before, after, 3)

    assert r.before is not None and r.before.qualified_name == "Repo.get"
    assert r.method == ResolutionMethod.RENAMED
    assert r.after is not None and r.after.qualified_name == "Repo.fetch"
    assert r.moved_to is None  # the holder of the line is the target itself


def test_added_decorator_extends_the_range() -> None:
    before = "def handler(req):\n    return req\n"
    after = "@app.post('/x')\ndef handler(req):\n    return req\n"

    r = resolve_target(before, after, 2)

    assert r.method == ResolutionMethod.SAME_NAME
    assert r.after is not None and r.after.start_line == 1


def test_nested_function_target() -> None:
    before = code("""
        def outer():
            def inner(x):
                return x * 2
            return inner
    """)

    r = resolve_target(before, before, 3)

    assert r.before is not None and r.before.qualified_name == "outer.inner"
    assert r.method == ResolutionMethod.SAME_NAME


def test_module_level_comment() -> None:
    r = resolve_target("import os\nX = 1\n", "import os\nX = 2\n", 2)

    assert r.method == ResolutionMethod.MODULE_LEVEL
    assert r.before is None and r.after is None


def test_deleted_function_is_not_found() -> None:
    before = "def gone(x):\n    return x\n\n\ndef keep():\n    return 1\n"
    after = "def keep():\n    return 1\n"

    r = resolve_target(before, after, 2)

    assert r.method == ResolutionMethod.NOT_FOUND
    assert r.after is None


def test_rename_plus_rewrite_below_threshold_is_not_found() -> None:
    before = "def calc(a, b):\n    return a + b\n"
    after = code("""
        def compute_everything(items, weights, bias):
            total = 0
            for item, weight in zip(items, weights):
                total += item * weight
            return total + bias
    """)

    r = resolve_target(before, after, 2)

    assert r.method == ResolutionMethod.NOT_FOUND
    assert r.similarity is not None and r.similarity < 0.6


def test_syntax_errors_are_reported_not_raised() -> None:
    r = resolve_target("def f(x):\n    return x\n", "def f(x:\n    return x\n", 2)

    assert r.after_has_errors and not r.before_has_errors


# ---------------------------------------------------------------- every dev fixture


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.meta.case_id)
def test_dev_fixture_target_is_resolved(fixture: Fixture) -> None:
    case = fixture.case
    assert case.before_code and case.after_code and case.anchor_line

    r = resolve_target(case.before_code, case.after_code, case.anchor_line)

    assert r.before is not None and r.before.name == fixture.meta.target_symbol
    assert r.after is not None
    if fixture.meta.case_id == "naming-006-rename-function-and-callers":
        assert (r.method, r.after.name) == (ResolutionMethod.RENAMED, "start_processing")
    else:
        assert r.method == ResolutionMethod.SAME_NAME
