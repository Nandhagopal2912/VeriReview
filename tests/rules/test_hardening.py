"""Phase 5.1 hardening: each relaxation has a positive test and an adversarial counterpart.

All snippets are new (not taken from dataset/heldout_fixtures).
"""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.requirements import extract_requirements
from verireview.rules import RuleStatus as S
from verireview.rules.analysis import call_arguments, function_parameters, scope_of

# ---------------------------------------------------------------- validation in a helper

HELPER_BEFORE = """
def store(repo, email):
    repo.put(email)
"""


def test_same_file_helper_check_satisfies() -> None:
    after = """
def require_email(address):
    if not address:
        raise ValueError("email required")


def store(repo, email):
    require_email(email)
    repo.put(email)
"""
    outcome = run_rule(req(C.VALIDATION, "Check `email` is not empty"), HELPER_BEFORE, after, 2)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["validation.checked_in_helper"] is True


def test_adversarial_helper_that_does_not_check() -> None:
    after = """
def require_email(address):
    print(address)


def store(repo, email):
    require_email(email)
    repo.put(email)
"""
    outcome = run_rule(req(C.VALIDATION, "Check `email` is not empty"), HELPER_BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED


def test_adversarial_helper_checking_the_wrong_kind() -> None:
    after = """
def require_email(address):
    if address is None:
        raise ValueError("email required")


def store(repo, email):
    require_email(email)
    repo.put(email)
"""
    ask = req(C.VALIDATION, "Check that `email` is between 3 and 254 characters")

    assert run_rule(ask, HELPER_BEFORE, after, 2).status == S.NOT_SATISFIED


def test_adversarial_helper_called_after_the_operation() -> None:
    after = """
def require_email(address):
    if not address:
        raise ValueError("email required")


def store(repo, email):
    repo.put(email)
    require_email(email)
"""
    outcome = run_rule(req(C.VALIDATION, "Check `email` is not empty"), HELPER_BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED


def test_imported_validator_is_inconclusive_not_accepted() -> None:
    after = HELPER_BEFORE.replace("    repo.put", "    check_email(email)\n    repo.put")

    outcome = run_rule(req(C.VALIDATION, "Validate `email`"), HELPER_BEFORE, after, 2)

    assert outcome.status == S.INCONCLUSIVE
    assert kinds(outcome)["validation.delegated"] is None


def test_adversarial_unrelated_imported_call_is_not_delegation() -> None:
    after = HELPER_BEFORE.replace("    repo.put", "    audit_trail(email)\n    repo.put")

    assert run_rule(req(C.VALIDATION, "Validate `email`"), HELPER_BEFORE, after, 2).status == (
        S.NOT_SATISFIED
    )


# ---------------------------------------------------------------- logging on a failure path

LOOKUP = """
def lookup(cache, key):
    value = cache.get(key)
    if value is None:
        value = fetch(key)
    return value
"""


def test_log_in_a_conditional_branch_counts() -> None:
    after = LOOKUP.replace(
        "        value = fetch", "        log.warning('miss %s', key)\n        value = fetch"
    )

    assert run_rule(req(C.ERROR_HANDLING, "Log a warning on a miss"), LOOKUP, after, 3).status == (
        S.SATISFIED
    )


def test_adversarial_log_outside_any_failure_path() -> None:
    after = LOOKUP.replace("    return value", "    log.warning('done')\n    return value")

    assert run_rule(req(C.ERROR_HANDLING, "Log a warning on a miss"), LOOKUP, after, 3).status == (
        S.NOT_SATISFIED
    )


# ---------------------------------------------------------------- KeyError avoided with .get()


def test_get_avoids_key_error() -> None:
    before = "def price(table, sku):\n    return table[sku]\n"
    after = "def price(table, sku):\n    return table.get(sku, 0)\n"

    assert run_rule(req(C.ERROR_HANDLING, "Handle the `KeyError`"), before, after, 2).status == (
        S.SATISFIED
    )


def test_adversarial_pre_existing_get_elsewhere_does_not_count() -> None:
    before = "def price(table, sku, opts):\n    opts.get('x')\n    return table[sku]\n"

    assert run_rule(req(C.ERROR_HANDLING, "Handle the `KeyError`"), before, before, 3).status == (
        S.NOT_SATISFIED
    )


# ---------------------------------------------------------------- API: related identifiers

FETCH = """
def fetch_invoice(invoice_id):
    row = load_invoice(invoice_id)
    return jsonify(row), 200
"""


def test_status_on_a_variable_derived_from_the_named_thing() -> None:
    after = FETCH.replace(
        "    return jsonify(row), 200",
        "    if row is None:\n        return jsonify({}), 404\n    return jsonify(row), 200",
    )
    ask = req(
        C.API_BEHAVIOR, "Return 404 when the invoice is missing", condition="the invoice is missing"
    )

    assert run_rule(ask, FETCH, after, 2).status == S.SATISFIED


def test_adversarial_status_on_an_unrelated_branch() -> None:
    after = FETCH.replace(
        "    return jsonify(row), 200",
        "    if debug_mode:\n        return jsonify({}), 404\n    return jsonify(row), 200",
    )
    ask = req(
        C.API_BEHAVIOR, "Return 404 when the invoice is missing", condition="the invoice is missing"
    )

    assert run_rule(ask, FETCH, after, 2).status == S.NOT_SATISFIED


def test_unmatchable_condition_is_inconclusive_not_accepted() -> None:
    after = FETCH.replace(
        "    return jsonify(row), 200",
        "    if debug_mode:\n        return jsonify({}), 404\n    return jsonify(row), 200",
    )
    ask = req(C.API_BEHAVIOR, "Return 404 when the thing is gone", condition="the thing is gone")

    assert run_rule(ask, FETCH, after, 2).status == S.INCONCLUSIVE


# ---------------------------------------------------------------- tests: decorators, empties

SUM = "def total(values):\n    return sum(values)\n"


def run_test_rule(description: str, test_code: str) -> S:
    return run_rule(
        req(C.TESTING, description), SUM, SUM, 2, tests_after={"tests/test_s.py": test_code}
    ).status


def test_parametrize_inputs_count() -> None:
    code = "@pytest.mark.parametrize('v', [None, -3])\ndef test_total(v):\n    total([v])\n"
    assert run_test_rule("Add a test with `None`", code) == S.SATISFIED
    assert run_test_rule("Add a test for a negative value", code) == S.SATISFIED


def test_empty_collection_counts_as_empty() -> None:
    assert run_test_rule("Add a test for an empty list", "def test_e():\n    total([])\n") == (
        S.SATISFIED
    )


def test_adversarial_non_empty_collection_is_not_empty() -> None:
    assert run_test_rule("Add a test for an empty list", "def test_e():\n    total([1])\n") == (
        S.NOT_SATISFIED
    )


# ---------------------------------------------------------------- extraction gaps


def test_respond_is_a_request_verb() -> None:
    req_ = extract_requirements("Respond with 404 if the user is not found.")

    assert req_.actionable
    assert req_.requirements[0].category == C.API_BEHAVIOR


def test_return_early_is_validation() -> None:
    req_ = extract_requirements("Return early if `items` is empty instead of crashing.")

    assert req_.requirements[0].category == C.VALIDATION


# ---------------------------------------------------------------- analysis helpers


def test_call_arguments() -> None:
    assert call_arguments("f(a, b=g(1, 2), c)", "f") == [(None, "a"), ("b", "g(1, 2)"), (None, "c")]
    assert call_arguments("f(x == 1)", "f") == [(None, "x == 1")]
    assert call_arguments("f", "f") == []


def test_function_parameters_skip_self() -> None:
    scope = scope_of("class A:\n    def m(self, x, y=1, *args, **kw):\n        pass\n")
    node = scope.function("m")

    assert node is not None
    assert function_parameters(node) == ["x", "y", "args", "kw"]
