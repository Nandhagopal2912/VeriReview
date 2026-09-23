from verireview.syntax import code_only

SOURCE = '''"""Module docstring."""
import os  # trailing comment


def f(x):
    """Function docstring
    over two lines."""
    # a full-line comment
    s = "# not a comment"
    return x  # done
'''


def test_comments_and_docstrings_are_blanked_keeping_lines() -> None:
    result = code_only(SOURCE)

    assert len(result.splitlines()) == len(SOURCE.splitlines())
    assert len(result) == len(SOURCE)
    lines = [line.rstrip() for line in result.splitlines()]
    assert lines[0] == ""
    assert lines[1] == "import os"
    assert lines[5:9] == ["", "", "", '    s = "# not a comment"']
    assert lines[9] == "    return x"


def test_strings_that_are_not_docstrings_are_kept() -> None:
    code = 'x = 1\n"""not a docstring: not the first statement"""\n'

    assert code_only(code) == code


def test_non_ascii_comment_keeps_the_text_valid() -> None:
    result = code_only("x = 1  # café → ok\n")

    assert result.rstrip() == "x = 1"
    assert result.endswith("\n")


def test_invalid_code_is_still_masked() -> None:
    assert code_only("def f(:\n    # note\n").splitlines()[1].strip() == ""
