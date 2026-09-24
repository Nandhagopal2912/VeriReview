"""Rules for `other` requests and suggestion blocks (Phase 10.1), each tested three ways."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleOutcome
from verireview.rules import RuleStatus as S

CODE = "def area(w, h):\n    # multiply the two sides\n    return w * h\n"


def run_other(description: str, before: str, after: str, anchor: int = 2) -> RuleOutcome:
    return run_rule(req(C.OTHER, description), before, after, anchor=anchor)


def run_suggestion(
    suggested: str, before: str, after: str, anchor: int = 3, category: C = C.OTHER
) -> RuleOutcome:
    requirement = req(category, "Apply the suggested change", suggested_code=suggested)
    return run_rule(requirement, before, after, anchor=anchor)


# ---------------------------------------------------------------- suggestion blocks


def test_positive_suggestion_applied_verbatim() -> None:
    after = CODE.replace("return w * h", "return float(w) * float(h)")
    outcome = run_suggestion("    return float(w) * float(h)", CODE, after)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["suggestion.applied"] is True


def test_positive_suggestion_reformatted_over_several_lines() -> None:
    before = "def f(a, b):\n    return g(a)\n"
    after = "def f(a, b):\n    return g(\n        a,\n        b,\n    )\n"
    assert run_suggestion("    return g(a, b)", before, after, anchor=2).status == S.SATISFIED


def test_negative_suggestion_ignored() -> None:
    outcome = run_suggestion("    return float(w) * float(h)", CODE, CODE)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["suggestion.not_applied"] is False


def test_adversarial_changed_differently_is_inconclusive() -> None:
    after = CODE.replace("return w * h", "return abs(w * h)")
    outcome = run_suggestion("    return float(w) * float(h)", CODE, after)

    assert outcome.status == S.INCONCLUSIVE


def test_adversarial_suggestion_elsewhere_in_file_does_not_count() -> None:
    before = CODE + "\n\ndef other(w, h):\n    return w * h\n"
    after = before.replace(
        "def other(w, h):\n    return w * h", "def other(w, h):\n    return float(w) * float(h)"
    )
    # The commented `return w * h` (line 3, in `area`) is unchanged; a copy in `other` changed.
    outcome = run_suggestion("    return float(w) * float(h)", before, after)

    assert outcome.status == S.NOT_SATISFIED


def test_indentation_only_suggestion_is_compared_exactly() -> None:
    before = (
        "def f(x):\n    try:\n        y = g(x)\nif y:\n            return y\n"
        "    except E:\n        pass\n"
    )
    fixed = before.replace("\nif y:", "\n        if y:")
    assert run_suggestion("        if y:", before, fixed, anchor=4).status == S.SATISFIED
    assert run_suggestion("        if y:", before, before, anchor=4).status == S.NOT_SATISFIED


def test_empty_suggestion_deletes_the_line() -> None:
    after = CODE.replace("    # multiply the two sides\n", "")
    assert run_suggestion("", CODE, after, anchor=2).status == S.SATISFIED
    assert run_suggestion("", CODE, CODE, anchor=2).status == S.NOT_SATISFIED


def test_suggested_rename_is_not_second_guessed_by_the_naming_rule() -> None:
    after = CODE.replace("return w * h", "return w * h  # area")
    outcome = run_suggestion("    return width * height", CODE, after, category=C.NAMING)

    assert outcome.status == S.INCONCLUSIVE


# ---------------------------------------------------------------- removal requests


def test_positive_remove_this_comment() -> None:
    after = CODE.replace("    # multiply the two sides\n", "")
    outcome = run_other("Remove this comment", CODE, after)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["removal.done"] is True


def test_negative_comment_still_there() -> None:
    outcome = run_other("I'd drop this comment", CODE, CODE)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["removal.still_present"] is False


def test_removal_of_a_named_identifier() -> None:
    before = "def area(w, h, unit):\n    return w * h\n"
    after = "def area(w, h):\n    return w * h\n"
    assert run_other("Remove `unit`, it is unused", before, after, 1).status == S.SATISFIED
    assert run_other("Remove `unit`, it is unused", before, before, 1).status == S.NOT_SATISFIED


def test_adversarial_remove_something_else_is_inconclusive() -> None:
    outcome = run_other("Remove the retry logic from the client", CODE, CODE)

    assert outcome.status == S.INCONCLUSIVE


# ---------------------------------------------------------------- docstrings


def test_positive_docstring_added() -> None:
    after = CODE.replace("def area(w, h):\n", 'def area(w, h):\n    """Area of a rectangle."""\n')
    outcome = run_other("Add a docstring", CODE, after, anchor=3)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["docstring.added"] is True


def test_negative_no_docstring() -> None:
    outcome = run_other("Add a docstring", CODE, CODE, anchor=3)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["docstring.missing"] is False


def test_adversarial_comment_is_not_a_docstring() -> None:
    after = CODE.replace("def area(w, h):\n", "def area(w, h):\n    # Area of a rectangle.\n")
    assert run_other("Add a docstring", CODE, after, anchor=3).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- use A instead of B

PATHS = "import os\n\n\ndef exists(p):\n    return os.path.exists(p)\n"


def test_positive_use_instead() -> None:
    after = "from pathlib import Path\n\n\ndef exists(p):\n    return Path(p).exists()\n"
    outcome = run_other("Use `Path` instead of `os.path`", PATHS, after, anchor=5)

    assert outcome.status == S.SATISFIED


def test_negative_old_still_used() -> None:
    outcome = run_other("Use `Path` instead of `os.path`", PATHS, PATHS, anchor=5)

    assert outcome.status == S.NOT_SATISFIED


def test_adversarial_both_used_is_inconclusive() -> None:
    after = "from pathlib import Path\nimport os\n\n\ndef exists(p):\n"
    after += "    return Path(p).exists() or os.path.exists(p)\n"
    assert run_other("Use `Path` instead of `os.path`", PATHS, after, anchor=5).status == (
        S.INCONCLUSIVE
    )


def test_unknown_request_shape_stays_inconclusive() -> None:
    outcome = run_other("Can we make this more elegant", CODE, CODE)

    assert outcome.status == S.INCONCLUSIVE
