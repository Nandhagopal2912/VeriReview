from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

CODE = """
def validate_username(username):
    if not username:
        raise ValueError("empty")
    return username


def other(x):
    return x
"""
EXISTING = """
from m import validate_username


def test_valid():
    assert validate_username("alice") == "alice"
"""


def run(description: str, tests_after: str | None, tests_before: str | None = EXISTING, **kw: str):
    return run_rule(
        req(C.TESTING, description, **kw),
        CODE,
        CODE,
        anchor=2,
        tests_before={"tests/test_m.py": tests_before} if tests_before else None,
        tests_after={"tests/test_m.py": tests_after} if tests_after else None,
    )


def test_positive_new_test_calls_function_with_requested_input() -> None:
    tests = (
        EXISTING
        + """

def test_empty_rejected():
    with pytest.raises(ValueError):
        validate_username("")
"""
    )
    outcome = run("Add a test for the empty username case", tests)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["testing.case_exercised"] is True


def test_negative_no_test_added() -> None:
    outcome = run("Add a test for the empty username case", None)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.no_new_test"] is False


def test_adversarial_test_named_for_the_case_but_not_exercising_it() -> None:
    tests = (
        EXISTING
        + """

def test_empty_username_case():
    assert validate_username("bob") == "bob"
"""
    )
    outcome = run("Add a test for the empty username case", tests)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.case_not_exercised"] is False


def test_adversarial_test_for_another_function() -> None:
    tests = (
        EXISTING
        + """

def test_other_empty():
    assert other("") == ""
"""
    )
    outcome = run("Add a test for `validate_username` with an empty value", tests)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.wrong_function"] is False


def test_unchanged_existing_test_is_not_new() -> None:
    outcome = run("Add a test for `validate_username`", EXISTING)

    # Existing test covers the function (no specific case asked): ADR-001 already present.
    assert outcome.status == S.SATISFIED
    assert outcome.already_present


def test_none_negative_timeout_and_numbers() -> None:
    body = (
        "def test_x():\n"
        "    validate_username(None)\n"
        "    validate_username(-1)\n"
        "    validate_username(1.0)\n"
    )
    assert run("Add a test with `None` input", body, None).status == S.SATISFIED
    assert run("Add a test for a negative value", body, None).status == S.SATISFIED
    assert run("Add a test with rate=1.0", body, None).status == S.SATISFIED
    assert run("Add a test for the timeout case", body, None).status == S.NOT_SATISFIED


def test_blank_accepts_whitespace() -> None:
    body = "def test_blank():\n    validate_username('   ')\n"

    assert run("Add a test for a blank name", body, None).status == S.SATISFIED
    assert run("Add a test for an empty name", body, None).status == S.NOT_SATISFIED


def test_class_target_cannot_be_the_function_under_test() -> None:
    code = "class A:\n    x = 1\n"
    outcome = run_rule(req(C.TESTING, "Add a test"), code, code, anchor=2)

    assert outcome.status == S.INCONCLUSIVE
