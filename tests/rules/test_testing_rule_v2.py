"""Testing rule, Phase 10.1: a new test must run, assert, expect the requested exception, target
its own scenario, and be new (not renamed). Positive, negative and adversarial cases per check."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import Requirement
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleOutcome
from verireview.rules import RuleStatus as S

CODE = """
def remove_stock(stock, sku, amount):
    if amount > stock[sku]:
        raise ValueError("not enough")
    stock[sku] -= amount
    return stock[sku]
"""
PATH = "tests/test_remove.py"
HEAD = "import pytest\n\nfrom inventory import remove_stock\n\n\n"


def run(
    description: str,
    tests_after: str,
    tests_before: str | None = None,
    siblings: list[Requirement] | None = None,
    code: str = CODE,
) -> RuleOutcome:
    return run_rule(
        req(C.TESTING, description),
        code,
        code,
        anchor=2,
        tests_before={PATH: tests_before} if tests_before else None,
        tests_after={PATH: tests_after},
        siblings=siblings,
    )


RAISES = HEAD + (
    "def test_remove_too_much():\n"
    "    with pytest.raises(ValueError):\n"
    "        remove_stock({'a': 1}, 'a', 5)\n"
)
WANT_RAISE = "Add a test that removing more than we have raises ValueError"


# ---------------------------------------------------------------- expected exception


def test_positive_test_expects_the_requested_exception() -> None:
    assert run(WANT_RAISE, RAISES).status == S.SATISFIED


def test_negative_test_without_any_assertion() -> None:
    body = HEAD + "def test_remove_too_much():\n    remove_stock({'a': 1}, 'a', 5)\n"
    outcome = run(WANT_RAISE, body)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.no_expectation"] is False


def test_adversarial_test_asserts_but_not_the_exception() -> None:
    body = HEAD + "def test_remove_too_much():\n    assert remove_stock({'a': 9}, 'a', 5) == 4\n"
    outcome = run(WANT_RAISE, body)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.case_not_exercised"] is False


def test_unittest_assert_raises_counts() -> None:
    body = (
        "import unittest\n\n\nclass T(unittest.TestCase):\n"
        "    def test_too_much(self):\n"
        "        with self.assertRaises(ValueError):\n"
        "            remove_stock({'a': 1}, 'a', 5)\n"
    )
    assert run(WANT_RAISE, body).status == S.SATISFIED


# ---------------------------------------------------------------- skipped tests


def test_adversarial_skipped_test_demonstrates_nothing() -> None:
    body = RAISES.replace("def test_", "@pytest.mark.skip(reason='TODO')\ndef test_")
    outcome = run(WANT_RAISE, body)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.test_skipped"] is False


def test_adversarial_xfail_and_skip_call_do_not_count() -> None:
    xfail = RAISES.replace("def test_", "@pytest.mark.xfail\ndef test_")
    skip_call = RAISES.replace("    with", "    pytest.skip('later')\n    with")

    assert run(WANT_RAISE, xfail).status == S.NOT_SATISFIED
    assert run(WANT_RAISE, skip_call).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- renamed, not new


def test_adversarial_renamed_test_is_not_a_new_test() -> None:
    before = HEAD + "def test_remove():\n    assert remove_stock({'a': 2}, 'a', 1) == 1\n"
    after = before.replace("def test_remove(", "def test_remove_out_of_stock(")
    outcome = run("Add a test for removing from an out-of-stock item", after, before)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.no_new_test"] is False


def test_negative_existing_test_does_not_cover_an_uncheckable_request() -> None:
    before = HEAD + "def test_remove():\n    assert remove_stock({'a': 2}, 'a', 1) == 1\n"
    after = before + "\n# a comment only\n"

    assert run("Add a test for restocking", after, before).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- one case per requirement


def test_single_item_case_needs_a_one_element_collection() -> None:
    code = "def median(xs):\n    return sorted(xs)[len(xs) // 2] if xs else None\n"
    empty_only = "def test_empty():\n    assert median([]) is None\n"
    single = "def test_single():\n    assert median([3]) == 3\n"

    assert run("Add a test for a single-item list", single, code=code).status == S.SATISFIED
    assert run("Add a test for a single-item list", empty_only, code=code).status == (
        S.NOT_SATISFIED
    )


def test_sibling_requirements_cannot_share_one_test() -> None:
    other = req(C.TESTING, "Add a test for removing more than in stock")
    outcome = run("Add a test for an unknown SKU", RAISES, siblings=[other])

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["testing.scenario_not_targeted"] is False


def test_sibling_requirement_with_its_own_test_is_satisfied() -> None:
    other = req(C.TESTING, "Add a test for an unknown SKU")
    outcome = run("Add a test for removing more than in stock", RAISES, siblings=[other])

    assert outcome.status == S.SATISFIED


def test_demonstrated_case_word_needs_no_scenario_word() -> None:
    other = req(C.TESTING, "Add a test for the empty string")
    body = HEAD + (
        "@pytest.mark.parametrize('v', [None, ''])\ndef test_blank(v):\n"
        "    assert remove_stock({'a': 1}, v, 0) == 1\n"
    )
    assert run("Add a test for None", body, siblings=[other]).status == S.SATISFIED


# ---------------------------------------------------------------- web handlers and fixtures

ROUTE = """
from flask import Flask

app = Flask(__name__)


@app.get("/orders/<int:order_id>")
def get_order(order_id):
    return {}, 404
"""


def test_positive_route_requested_through_the_test_client() -> None:
    body = (
        "def test_unknown_order():\n"
        "    client = app.test_client()\n"
        "    assert client.get('/orders/999').status_code == 404\n"
    )
    outcome = run_rule(
        req(C.TESTING, "Add a test that checks the 404 case"),
        ROUTE,
        ROUTE,
        anchor=8,
        tests_after={PATH: body},
    )
    assert outcome.status == S.SATISFIED


def test_adversarial_client_call_to_another_url_does_not_count() -> None:
    body = (
        "def test_unknown_user():\n"
        "    client = app.test_client()\n"
        "    assert client.get('/users/999').status_code == 404\n"
    )
    outcome = run_rule(
        req(C.TESTING, "Add a test that checks the 404 case"),
        ROUTE,
        ROUTE,
        anchor=8,
        tests_after={PATH: body},
    )
    assert outcome.status == S.NOT_SATISFIED


def test_test_through_an_unseen_fixture_is_inconclusive() -> None:
    body = "def test_negative(run_scenario):\n    assert run_scenario('negative').rejected\n"
    outcome = run("Add a test for negative amounts", body)

    assert outcome.status == S.INCONCLUSIVE
    assert kinds(outcome)["testing.opaque_fixture"] is None


def test_builtin_fixture_is_not_opaque() -> None:
    body = "def test_negative(tmp_path):\n    assert tmp_path.exists()\n"

    assert run("Add a test for negative amounts", body).status == S.NOT_SATISFIED
