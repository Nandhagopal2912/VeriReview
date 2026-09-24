"""Naming rule, Phase 10.1: a compatibility alias keeps the old name without undoing a rename."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleStatus as S

BEFORE = "def get_user(db, uid):\n    return db.find(uid)\n\n\ndef profile(db, uid):\n"
BEFORE += "    return get_user(db, uid).profile\n"
ASK = req(C.NAMING, "Rename `get_user` to `fetch_user`")


def test_positive_rename_with_deprecated_alias() -> None:
    after = BEFORE.replace("get_user", "fetch_user") + "\n\nget_user = fetch_user\n"
    outcome = run_rule(ASK, BEFORE, after, anchor=1)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["naming.compatibility_alias"] is None


def test_negative_old_name_still_called() -> None:
    after = BEFORE.replace("def get_user", "def fetch_user") + "\n\nget_user = fetch_user\n"
    outcome = run_rule(ASK, BEFORE, after, anchor=1)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["naming.old_name_remains"] is False


def test_adversarial_alias_the_other_way_round_is_no_rename() -> None:
    after = BEFORE + "\n\nfetch_user = get_user\n"
    outcome = run_rule(ASK, BEFORE, after, anchor=1)

    assert outcome.status == S.NOT_SATISFIED
