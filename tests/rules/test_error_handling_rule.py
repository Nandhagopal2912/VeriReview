from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

BEFORE = """
def create(db, customer_id, data):
    return db.insert(data)
"""


def wrap(handler_body: str, exc: str = "DatabaseError") -> str:
    return (
        "def create(db, customer_id, data):\n"
        "    try:\n"
        "        return db.insert(data)\n"
        f"    except {exc} as err:\n"
        f"{handler_body}\n"
    )


def test_positive_catch_log_and_raise() -> None:
    after = wrap(
        "        logger.exception('failed for %s', customer_id)\n"
        "        raise ServiceError('x') from err"
    )
    for description in (
        "Handle `DatabaseError` from the insert",
        "Log the failure with the customer id",
        "Raise a `ServiceError` instead",
    ):
        outcome = run_rule(req(C.ERROR_HANDLING, description), BEFORE, after, 2)
        assert outcome.status == S.SATISFIED, description


def test_negative_nothing_handled() -> None:
    outcome = run_rule(req(C.ERROR_HANDLING, "Handle `DatabaseError`"), BEFORE, BEFORE, 2)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.catch_DatabaseError"] is False


def test_adversarial_swallowing_handler_does_not_count() -> None:
    after = wrap("        pass", exc="Exception")

    outcome = run_rule(req(C.ERROR_HANDLING, "Catch `DatabaseError`"), BEFORE, after, 2)

    assert outcome.status == S.NOT_SATISFIED
    assert "swallows" in outcome.evidence[0].detail


def test_adversarial_log_without_requested_value() -> None:
    after = wrap("        logger.exception('failed')\n        raise")

    outcome = run_rule(
        req(C.ERROR_HANDLING, "Log the failure (with the customer id) before re-raising"),
        BEFORE,
        after,
        2,
    )

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.log"] is False
    assert kinds(outcome)["error_handling.re-raise"] is True


def test_retry_requires_a_second_attempt() -> None:
    once = wrap("        raise FetchError('x')", exc="Timeout")
    twice = (
        "def create(db, customer_id, data):\n"
        "    try:\n"
        "        return db.insert(data)\n"
        "    except Timeout:\n"
        "        return db.insert(data)\n"
    )
    ask = req(C.ERROR_HANDLING, "Retry once on timeout")

    assert run_rule(ask, BEFORE, once, 2).status == S.NOT_SATISFIED
    assert run_rule(ask, BEFORE, twice, 2).status == S.SATISFIED


def test_fallback_value() -> None:
    after = wrap("        return dict(DEFAULTS)", exc="FileNotFoundError")

    ok = req(
        C.ERROR_HANDLING,
        "fall back to `DEFAULTS` (for `FileNotFoundError`)",
        target="FileNotFoundError",
    )
    missing = req(
        C.ERROR_HANDLING,
        "fall back to `DEFAULTS` (for `PermissionError`)",
        target="PermissionError",
    )

    assert run_rule(ok, BEFORE, after, 2).status == S.SATISFIED
    assert run_rule(missing, BEFORE, after, 2).status == S.NOT_SATISFIED


def test_raised_target_is_not_treated_as_caught() -> None:
    after = wrap("        raise ServiceError('x') from err")

    outcome = run_rule(
        req(C.ERROR_HANDLING, "raise a `ServiceError` instead", target="ServiceError"),
        BEFORE,
        after,
        2,
    )

    assert outcome.status == S.SATISFIED


def test_generic_handle_accepts_a_new_guard() -> None:
    before = "def avg(total, count):\n    return total / count\n"
    after = (
        "def avg(total, count):\n    if count == 0:\n        return 0.0\n    return total / count\n"
    )

    outcome = run_rule(req(C.ERROR_HANDLING, "handle that case (return 0.0)"), before, after, 2)

    assert outcome.status == S.SATISFIED


def test_already_present_adr_001() -> None:
    code = wrap("        logger.error('x')\n        raise")

    outcome = run_rule(req(C.ERROR_HANDLING, "Re-raise after handling"), code, code, 3)

    assert outcome.status == S.SATISFIED and outcome.already_present
