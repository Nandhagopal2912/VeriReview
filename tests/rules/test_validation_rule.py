from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

BEFORE = """
def save(db, username, age):
    db.insert(username, age)
"""


def after_with(check: str) -> str:
    return BEFORE.replace("    db.insert", f"{check}\n    db.insert")


def test_positive_none_check_that_raises_before_the_operation() -> None:
    after = after_with("    if username is None:\n        raise ValueError('required')")

    outcome = run_rule(req(C.VALIDATION, "Add a None check for `username`"), BEFORE, after, 2)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["validation.none_check"] is True


def test_negative_no_check() -> None:
    outcome = run_rule(req(C.VALIDATION, "Add a None check for `username`"), BEFORE, BEFORE, 2)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.no_check"] is False


def test_adversarial_check_on_another_variable() -> None:
    after = after_with("    if age is None:\n        raise ValueError('required')")

    outcome = run_rule(req(C.VALIDATION, "Add a None check for `username`"), BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.check_on_other_variable"] is False


def test_adversarial_check_after_the_operation() -> None:
    after = BEFORE + "    if username is None:\n        raise ValueError('required')\n"

    outcome = run_rule(req(C.VALIDATION, "Add a None check for `username`"), BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.check_after_operation"] is False


def test_adversarial_check_that_only_logs() -> None:
    after = after_with("    if username is None:\n        print('missing')")

    outcome = run_rule(req(C.VALIDATION, "Add a None check for `username`"), BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.check_does_not_reject"] is False


def test_adversarial_docstring_mentioning_validation() -> None:
    after = BEFORE.replace("    db.insert", '    """Validates username."""\n    db.insert')

    outcome = run_rule(req(C.VALIDATION, "Validate `username`"), BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED


def test_kind_must_match_type_check_requested() -> None:
    range_only = after_with("    if age < 0 or age > 150:\n        raise ValueError('range')")
    typed = after_with("    if not isinstance(age, int):\n        raise TypeError('int')")

    ask = req(C.VALIDATION, "Validate that `age` is an int")
    assert run_rule(ask, BEFORE, range_only, 2).status == S.NOT_SATISFIED
    assert run_rule(ask, BEFORE, typed, 2).status == S.SATISFIED


def test_all_requested_kinds_are_needed() -> None:
    empty_only = after_with("    if not username:\n        raise ValueError('empty')")
    both = after_with("    if not username or len(username) > 32:\n        raise ValueError('x')")

    ask = req(C.VALIDATION, "Validate `username` (non-empty, max 32 chars)")
    assert run_rule(ask, BEFORE, empty_only, 2).status == S.NOT_SATISFIED
    assert run_rule(ask, BEFORE, both, 2).status == S.SATISFIED


def test_early_return_counts_as_rejection() -> None:
    after = after_with("    if not username:\n        return None")

    outcome = run_rule(req(C.VALIDATION, "Check `username` is not empty"), BEFORE, after, 2)

    assert outcome.status == S.SATISFIED


def test_assert_counts_as_rejection() -> None:
    after = after_with("    assert username is not None")

    assert run_rule(
        req(C.VALIDATION, "Assert `username` is not None"), BEFORE, after, 2
    ).status == (S.SATISFIED)


def test_already_present_adr_001() -> None:
    code = after_with("    if age <= 0:\n        raise ValueError('positive')")

    outcome = run_rule(req(C.VALIDATION, "Validate that `age` is positive"), code, code, 4)

    assert outcome.status == S.SATISFIED
    assert outcome.already_present
    assert kinds(outcome)["already_present"] is True


def test_no_variable_is_inconclusive() -> None:
    outcome = run_rule(req(C.VALIDATION, "Validate the input"), BEFORE, BEFORE, 2)

    assert outcome.status == S.INCONCLUSIVE
