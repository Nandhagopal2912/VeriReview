from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

BEFORE = """
def save_user(db, usr):
    record = {"name": usr}
    db.insert(record)
    return record
"""


def test_positive_parameter_renamed_everywhere() -> None:
    outcome = run_rule(
        req(C.NAMING, "Rename `usr` to `username`", target="usr"),
        BEFORE,
        BEFORE.replace("usr", "username"),
        anchor=1,
    )

    assert outcome.status == S.SATISFIED
    assert kinds(outcome) == {"naming.old_name_removed": True, "naming.new_name_used": True}


def test_negative_old_name_still_used() -> None:
    after = (
        BEFORE.replace("def save_user(db, usr)", "def save_user(db, username)")
        .replace('{"name": usr}', '{"name": username}')
        .replace("return record", "return usr")
    )

    outcome = run_rule(req(C.NAMING, "Rename `usr` to `username`", target="usr"), BEFORE, after, 1)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["naming.old_name_remains"] is False


def test_adversarial_comment_mentioning_new_name_is_not_a_rename() -> None:
    after = BEFORE.replace("    record =", "    # usr is really the username\n    record =")

    outcome = run_rule(req(C.NAMING, "Rename `usr` to `username`", target="usr"), BEFORE, after, 1)

    assert outcome.status == S.NOT_SATISFIED


def test_adversarial_renamed_to_a_different_name_than_demanded() -> None:
    outcome = run_rule(
        req(C.NAMING, "Rename `usr` to `username`", target="usr"),
        BEFORE,
        BEFORE.replace("usr", "user_name"),
        anchor=1,
    )

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["naming.new_name_missing"] is False


def test_example_name_is_not_mandatory() -> None:
    outcome = run_rule(
        req(C.NAMING, "Use a descriptive name for `usr`, e.g. `username`", target="usr"),
        BEFORE,
        BEFORE.replace("usr", "account_name"),
        anchor=1,
    )

    assert outcome.status == S.SATISFIED


def test_function_rename_checks_callers_file_wide() -> None:
    before = "def proc(o):\n    return o\n\n\ndef run(o):\n    return proc(o)\n"
    renamed_def_only = before.replace("def proc", "def start")

    outcome = run_rule(
        req(C.NAMING, "Rename `proc` to `start`", target="proc"), before, renamed_def_only, 1
    )

    assert outcome.status == S.NOT_SATISFIED  # the caller still uses `proc`


def test_arrow_notation() -> None:
    outcome = run_rule(
        req(C.NAMING, "nit: `usr` -> `username`"), BEFORE, BEFORE.replace("usr", "username"), 1
    )

    assert outcome.status == S.SATISFIED


def test_other_requirement_rename_in_comment_does_not_leak() -> None:
    before = "def calc(items):\n    tmp = 0\n    return tmp + len(items)\n"
    after = before.replace("tmp", "total_price")

    outcome = run_rule(
        req(C.NAMING, "please give `calc` a real name like `calculate_total`", target="calc"),
        before,
        after,
        2,
        comment="Rename `tmp` to `total_price`, and please give `calc` a real name like "
        "`calculate_total`.",
    )

    assert outcome.status == S.NOT_SATISFIED  # `calc` itself was not renamed


def test_already_named_is_present_adr_001() -> None:
    code = "def f(username):\n    return username\n"

    outcome = run_rule(req(C.NAMING, "Rename `usr` to `username`"), code, code, 1)

    assert outcome.status == S.SATISFIED
    assert outcome.already_present


def test_no_identifiable_old_name_is_inconclusive() -> None:
    outcome = run_rule(req(C.NAMING, "Maybe a better name here?"), BEFORE, BEFORE, 1)

    assert outcome.status == S.INCONCLUSIVE
