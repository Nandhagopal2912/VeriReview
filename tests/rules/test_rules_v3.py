"""Rules, Phase 10.3: unreachable checks and handlers, discarded HTTP exceptions, polarity of
range checks, checks behind an unrelated flag, type nouns, calls named as `open()`, uncollected
test files and unshown test scenarios. Positive, negative and adversarial cases per check."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

# ---------------------------------------------------------------- unreachable guards

PAGE = "def page(items, limit):\n    return items[:limit]\n"
WANT_NOT_NEGATIVE = "Validate that `limit` is not negative"


def test_positive_guard_before_the_return() -> None:
    after = (
        "def page(items, limit):\n    if limit < 0:\n        raise ValueError('limit')\n"
        "    return items[:limit]\n"
    )
    outcome = run_rule(req(C.VALIDATION, WANT_NOT_NEGATIVE), PAGE, after, 2)

    assert outcome.status == S.SATISFIED


def test_adversarial_guard_after_the_return_never_runs() -> None:
    after = PAGE + "    if limit < 0:\n        raise ValueError('limit')\n"
    outcome = run_rule(req(C.VALIDATION, WANT_NOT_NEGATIVE), PAGE, after, 2)

    assert outcome.status == S.NOT_SATISFIED


# ---------------------------------------------------------------- polarity


def test_negative_inverted_condition_rejects_the_valid_values() -> None:
    after = (
        "def page(items, limit):\n    if limit >= 0:\n        raise ValueError('limit')\n"
        "    return items[:limit]\n"
    )
    outcome = run_rule(req(C.VALIDATION, WANT_NOT_NEGATIVE), PAGE, after, 2)

    assert outcome.status == S.NOT_SATISFIED


def test_positive_assert_reads_the_other_way_round() -> None:
    after = "def page(items, limit):\n    assert limit >= 0\n    return items[:limit]\n"
    outcome = run_rule(req(C.VALIDATION, WANT_NOT_NEGATIVE), PAGE, after, 2)

    assert outcome.status == S.SATISFIED


def test_adversarial_between_with_the_bounds_swapped() -> None:
    ask = req(C.VALIDATION, "Validate that `limit` is between 1 and 100")
    right = (
        "def page(items, limit):\n    if limit < 1 or limit > 100:\n"
        "        raise ValueError('limit')\n    return items[:limit]\n"
    )
    inverted = right.replace("limit < 1 or limit > 100", "1 <= limit <= 100")

    assert run_rule(ask, PAGE, right, 2).status == S.SATISFIED
    assert run_rule(ask, PAGE, inverted, 2).status == S.NOT_SATISFIED


def test_condition_that_cannot_be_evaluated_is_not_second_guessed() -> None:
    after = (
        "def page(items, limit):\n    if limit < minimum(items) or limit < 0:\n"
        "        raise ValueError('limit')\n    return items[:limit]\n"
    )
    outcome = run_rule(req(C.VALIDATION, WANT_NOT_NEGATIVE), PAGE, after, 2)

    assert outcome.status == S.SATISFIED


# ---------------------------------------------------------------- checks behind a flag

MOVE = "def move(source, target):\n    target.extend(source)\n"
WANT_DISTINCT = "Validate that `source` and `target` are not the same list"


def flagged(flag_line: str) -> str:
    return (
        f"{flag_line}\n\n\ndef move(source, target):\n"
        "    if DEBUG and source is target:\n        raise ValueError('same list')\n"
        "    target.extend(source)\n"
    )


def test_negative_check_behind_a_flag_that_is_false() -> None:
    outcome = run_rule(req(C.VALIDATION, WANT_DISTINCT), MOVE, flagged("DEBUG = False"), 2)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.check_disabled_by_flag"] is False


def test_adversarial_check_behind_a_flag_of_unknown_value() -> None:
    after = flagged("DEBUG = settings.debug")
    outcome = run_rule(req(C.VALIDATION, WANT_DISTINCT), MOVE, after, 2)

    assert outcome.status == S.INCONCLUSIVE
    assert kinds(outcome)["validation.check_behind_flag"] is None


def test_positive_flag_that_is_true_keeps_the_check() -> None:
    outcome = run_rule(req(C.VALIDATION, WANT_DISTINCT), MOVE, flagged("DEBUG = True"), 2)

    assert outcome.status == S.SATISFIED


def test_none_check_on_the_variable_itself_is_not_a_flag() -> None:
    after = (
        "def move(source, target):\n"
        "    if source is not None and source is target:\n"
        "        raise ValueError('same list')\n    target.extend(source)\n"
    )
    outcome = run_rule(req(C.VALIDATION, WANT_DISTINCT), MOVE, after, 2)

    assert outcome.status == S.SATISFIED


# ---------------------------------------------------------------- type nouns

SPAN = "def span(start, end):\n    return end - start\n"
WANT_DATES = "Validate that `start` and `end` are dates"


def test_positive_isinstance_check_for_dates() -> None:
    after = (
        "def span(start, end):\n"
        "    if not isinstance(start, date) or not isinstance(end, date):\n"
        "        raise TypeError('dates')\n    return end - start\n"
    )
    assert run_rule(req(C.VALIDATION, WANT_DATES), SPAN, after, 2).status == S.SATISFIED


def test_adversarial_order_check_is_not_a_type_check() -> None:
    after = (
        "def span(start, end):\n    if start > end:\n        raise ValueError('order')\n"
        "    return end - start\n"
    )
    assert run_rule(req(C.VALIDATION, WANT_DATES), SPAN, after, 2).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- unreachable handlers

LOAD = "import json\n\n\ndef load(text):\n    return json.loads(text)\n"


def test_positive_handler_around_the_call() -> None:
    after = (
        "import json\n\n\ndef load(text):\n    try:\n        return json.loads(text)\n"
        "    except ValueError:\n        return {}\n"
    )
    outcome = run_rule(req(C.ERROR_HANDLING, "Handle the ValueError"), LOAD, after, 5)

    assert outcome.status == S.SATISFIED


def test_adversarial_handler_after_the_return_handles_nothing() -> None:
    after = LOAD + (
        "    try:\n        return json.loads(text)\n    except ValueError:\n        return {}\n"
    )
    outcome = run_rule(req(C.ERROR_HANDLING, "Handle the ValueError"), LOAD, after, 5)

    assert outcome.status == S.NOT_SATISFIED


# ---------------------------------------------------------------- a call named as `open()`

READ = "def read(path):\n    size = len(path)\n    return open(path).read(), size\n"
WANT_OPEN = "`open()` raises FileNotFoundError when the file is missing; handle that"


def test_positive_handler_protects_the_named_call() -> None:
    after = (
        "def read(path):\n    size = len(path)\n    try:\n"
        "        return open(path).read(), size\n"
        "    except FileNotFoundError:\n        return '', size\n"
    )
    ask = req(C.ERROR_HANDLING, WANT_OPEN)
    assert run_rule(ask, READ, after, 3, comment=WANT_OPEN).status == S.SATISFIED


def test_adversarial_handler_around_another_statement() -> None:
    after = (
        "def read(path):\n    try:\n        size = len(path)\n"
        "    except FileNotFoundError:\n        size = 0\n"
        "    return open(path).read(), size\n"
    )
    ask = req(C.ERROR_HANDLING, WANT_OPEN)
    assert run_rule(ask, READ, after, 3, comment=WANT_OPEN).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- discarded HTTP exceptions

API_HEAD = "from fastapi import HTTPException\n\nITEMS = {}\n\n\n"
ITEM = API_HEAD + "def item(item_id):\n"
API_BEFORE = ITEM + "    return ITEMS[item_id]\n"
WANT_404 = "Return 404 if `item_id` is not found"


def test_positive_raised_http_exception() -> None:
    after = ITEM + (
        "    if item_id not in ITEMS:\n        raise HTTPException(status_code=404)\n"
        "    return ITEMS[item_id]\n"
    )
    assert run_rule(req(C.API_BEHAVIOR, WANT_404), API_BEFORE, after, 7).status == S.SATISFIED


def test_adversarial_http_exception_built_but_not_raised() -> None:
    after = ITEM + (
        "    if item_id not in ITEMS:\n        HTTPException(status_code=404)\n"
        "    return ITEMS[item_id]\n"
    )
    outcome = run_rule(req(C.API_BEHAVIOR, WANT_404), API_BEFORE, after, 7)

    assert outcome.status == S.NOT_SATISFIED


def test_positive_abort_as_a_statement_still_acts() -> None:
    before = "from flask import abort\n\nITEMS = {}\n\n\ndef item(item_id):\n"
    after = before + (
        "    if item_id not in ITEMS:\n        abort(404)\n    return ITEMS[item_id]\n"
    )
    before += "    return ITEMS[item_id]\n"
    assert run_rule(req(C.API_BEHAVIOR, WANT_404), before, after, 7).status == S.SATISFIED


# ---------------------------------------------------------------- testing: collected files

CODE = "def is_leap(year):\n    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)\n"
HEAD = "from calendar_utils import is_leap\n\n\n"
LEAP_TEST = HEAD + "def test_2024_is_leap():\n    assert is_leap(2024)\n"


def run_testing(description: str, path: str, tests_after: str) -> S:
    return run_rule(
        req(C.TESTING, description), CODE, CODE, anchor=2, tests_after={path: tests_after}
    ).status


def test_positive_test_in_a_collected_file() -> None:
    assert run_testing("Add a test for `is_leap`", "tests/test_dates.py", LEAP_TEST) == (
        S.SATISFIED
    )


def test_adversarial_test_in_a_file_runners_do_not_collect() -> None:
    outcome = run_rule(
        req(C.TESTING, "Add a test for `is_leap`"),
        CODE,
        CODE,
        anchor=2,
        tests_after={"tests/leap_checks.py": LEAP_TEST},
    )

    assert outcome.status == S.INCONCLUSIVE
    assert kinds(outcome)["testing.file_not_collected"] is None


def test_unittest_style_suffix_is_collected() -> None:
    assert run_testing("Add a test for `is_leap`", "tests/dates_test.py", LEAP_TEST) == (
        S.SATISFIED
    )


# ---------------------------------------------------------------- testing: the scenario


def test_positive_test_names_the_requested_scenario() -> None:
    body = HEAD + "def test_century_is_not_leap():\n    assert not is_leap(1900)\n"
    ask = "Add a test for a century year for `is_leap`"
    assert run_testing(ask, "tests/test_dates.py", body) == S.SATISFIED


def test_adversarial_ordinary_test_does_not_show_the_scenario() -> None:
    ask = "Add a test for a century year for `is_leap`"
    outcome = run_rule(
        req(C.TESTING, ask), CODE, CODE, anchor=2, tests_after={"tests/test_dates.py": LEAP_TEST}
    )

    assert outcome.status == S.INCONCLUSIVE
    assert kinds(outcome)["testing.scenario_not_shown"] is None


def test_parameter_name_is_not_a_scenario() -> None:
    # "a leap year": "leap" is the function's name, "year" its parameter.
    assert run_testing("Add a test for a leap year", "tests/test_dates.py", LEAP_TEST) == (
        S.SATISFIED
    )


# ---------------------------------------------------------------- other: removal statements

TOTAL = "def total(xs):\n    unused = len(xs)\n    return sum(xs)\n"
WITHOUT = "def total(xs):\n    return sum(xs)\n"


def run_other(description: str, before: str, after: str, anchor: int = 2) -> S:
    return run_rule(req(C.OTHER, description), before, after, anchor=anchor).status


def test_positive_no_longer_used_line_removed() -> None:
    assert run_other("No longer used", TOTAL, WITHOUT) == S.SATISFIED


def test_negative_superfluous_line_still_there() -> None:
    other_change = TOTAL.replace("sum(xs)", "sum(xs) + 0")
    assert run_other("This duplicates the line above.", TOTAL, other_change) == (S.NOT_SATISFIED)


def test_positive_named_identifier_no_longer_needed() -> None:
    assert run_other("`unused` is no longer needed", TOTAL, WITHOUT) == S.SATISFIED


def test_adversarial_line_edited_but_identifier_kept() -> None:
    edited = TOTAL.replace("unused = len(xs)", "unused = len(xs) or 0")
    assert run_other("`unused` is no longer needed", TOTAL, edited) == S.NOT_SATISFIED


# ---------------------------------------------------------------- other: literal comments

ASK_REF = "add a ref to the issue on the first line: `# GH#63221`"


def test_positive_literal_comment_added() -> None:
    after = TOTAL.replace("    unused", "    # GH#63221\n    unused")
    assert run_other(ASK_REF, TOTAL, after) == S.SATISFIED


def test_negative_literal_comment_missing() -> None:
    after = TOTAL.replace("    unused", "    # see the issue\n    unused")
    assert run_other(ASK_REF, TOTAL, after) == S.NOT_SATISFIED


def test_adversarial_comment_already_there_is_not_new() -> None:
    before = "# GH#63221\n" + TOTAL
    after = before.replace("sum(xs)", "sum(xs) + 0")
    assert run_other(ASK_REF, before, after, anchor=3) == S.INCONCLUSIVE


def test_adversarial_comment_described_in_words_stays_inconclusive() -> None:
    after = TOTAL.replace("    unused", "    # explain\n    unused")
    assert run_other("add a comment explaining this", TOTAL, after) == S.INCONCLUSIVE
