from helpers.cases import make_case
from verireview.contracts import ReviewCase
from verireview.ingestion import make_unified_diff
from verireview.semantic import CodeChunk, change_chunks, code_change_text

BEFORE = "def save(db, username):\n    db.insert(username)\n"


def case(after: str, **kw: object) -> ReviewCase:
    base = make_case(BEFORE, after, 2)
    diff = make_unified_diff(BEFORE, after, "m.py", "m.py")
    return base.model_copy(update={"unified_diff": diff, **kw})


def test_added_code_becomes_located_chunks() -> None:
    after = (
        "def save(db, username):\n"
        "    if username is None:\n"
        "        raise ValueError('username required')\n"
        "    db.insert(username)\n"
        "    log(username)\n"
    )

    assert change_chunks(case(after)) == [
        CodeChunk(
            "m.py",
            2,
            3,
            "if username is None:\n    raise ValueError('username required')",
        ),
        CodeChunk("m.py", 5, 5, "log(username)"),
    ]


def test_comment_only_change_has_no_code() -> None:
    after = "def save(db, username):\n    # TODO: validate username\n    db.insert(username)\n"

    assert change_chunks(case(after)) == []
    assert code_change_text(case(after)) == ""


def test_comments_and_docstrings_inside_added_code_are_dropped() -> None:
    after = (
        "def save(db, username):\n"
        '    """Validate the username (docstring)."""\n'
        "    check(username)  # validate username\n"
        "    db.insert(username)\n"
    )

    assert code_change_text(case(after)) == "check(username)"


def test_new_test_code_is_a_chunk_of_the_test_file() -> None:
    before_tests = "def test_a():\n    pass\n"
    after_tests = before_tests + "\n\ndef test_b():\n    # empty input\n    save(None)\n"
    c = case(
        BEFORE,
        test_files={"tests/t.py": after_tests},
        test_files_before={"tests/t.py": before_tests},
    )

    # Inserted lines 3-7; the span shrinks to the code actually kept (blank lines dropped).
    assert change_chunks(c) == [CodeChunk("tests/t.py", 5, 7, "def test_b():\n    save(None)")]


def test_no_after_code_uses_tests_only() -> None:
    c = case(BEFORE, after_code=None, test_files={"t.py": "x = 1\n"})

    assert change_chunks(c) == [CodeChunk("t.py", 1, 1, "x = 1")]
