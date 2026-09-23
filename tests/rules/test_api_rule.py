from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

BEFORE = """
def get_order(order_id):
    order = find_order(order_id)
    return jsonify(order), 200
"""


def branch(code: int) -> str:
    return BEFORE.replace(
        "    return jsonify(order), 200",
        f"    if order is None:\n        return jsonify({{}}), {code}\n"
        "    return jsonify(order), 200",
    )


ASK_404 = req(
    C.API_BEHAVIOR, "Return 404 when the `order` doesn't exist", condition="order missing"
)


def test_positive_status_on_the_right_branch() -> None:
    outcome = run_rule(ASK_404, BEFORE, branch(404), 2)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["api.status_returned"] is True


def test_negative_status_never_returned() -> None:
    outcome = run_rule(ASK_404, BEFORE, BEFORE, 2)

    assert outcome.status == S.NOT_SATISFIED


def test_adversarial_wrong_status_on_the_branch_is_named() -> None:
    outcome = run_rule(ASK_404, BEFORE, branch(400), 2)

    assert outcome.status == S.NOT_SATISFIED
    assert "returns HTTP 400" in next(
        e.detail for e in outcome.evidence if e.kind == "api.wrong_status"
    )


def test_adversarial_status_only_in_a_comment() -> None:
    after = BEFORE.replace(
        "    return jsonify", "    # TODO: return 404 when missing\n    return jsonify"
    )

    assert run_rule(ASK_404, BEFORE, after, 2).status == S.NOT_SATISFIED


def test_adversarial_status_on_the_else_branch() -> None:
    after = BEFORE.replace(
        "    return jsonify(order), 200",
        "    if order is None:\n        return jsonify({}), 200\n"
        "    else:\n        return jsonify(order), 404",
    )

    assert run_rule(ASK_404, BEFORE, after, 2).status == S.NOT_SATISFIED


def test_statuses_marked_as_current_or_wrong_are_not_wanted() -> None:
    after = BEFORE.replace(", 200", ", 201")

    ask = req(C.API_BEHAVIOR, "Creating a resource should return `201 Created`, not 200.")
    assert run_rule(ask, BEFORE, after, 2).status == S.SATISFIED
    ask_now = req(C.API_BEHAVIOR, "Return HTTP 404 for a missing order, right now this is a 500")
    assert run_rule(ask_now, BEFORE, branch(404), 2).status == S.SATISFIED


def test_abort_and_http_exception_count() -> None:
    abort = BEFORE.replace(
        "    return jsonify", "    if order is None:\n        abort(404)\n    return jsonify"
    )
    raised = BEFORE.replace(
        "    return jsonify",
        "    if order is None:\n        raise HTTPException(status_code=404)\n    return jsonify",
    )

    assert run_rule(ASK_404, BEFORE, abort, 2).status == S.SATISFIED
    assert run_rule(ASK_404, BEFORE, raised, 2).status == S.SATISFIED


def test_header_requirement() -> None:
    after = BEFORE.replace(", 200", ", 201, {'Location': url}")

    ask = req(C.API_BEHAVIOR, "include a `Location` header")
    assert run_rule(ask, BEFORE, after, 2).status == S.SATISFIED
    assert run_rule(ask, BEFORE, BEFORE, 2).status == S.NOT_SATISFIED


def test_already_present_adr_001() -> None:
    outcome = run_rule(ASK_404, branch(404), branch(404), 2)

    assert outcome.status == S.SATISFIED and outcome.already_present


def test_no_status_named_is_inconclusive() -> None:
    assert run_rule(req(C.API_BEHAVIOR, "Make it RESTful"), BEFORE, BEFORE, 2).status == (
        S.INCONCLUSIVE
    )
