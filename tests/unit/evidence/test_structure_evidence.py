from textwrap import dedent

from helpers.cases import REQUIREMENT, make_case
from verireview.contracts import Evidence
from verireview.evidence.structure import MAX_FACT_EVIDENCE, structural_evidence

BEFORE = dedent("""\
    def save_user(db, username):
        record = {"name": username}
        db.insert("users", record)
        return record


    def unrelated():
        return 1
""")


def run(before: str | None, after: str | None, anchor: int | None = 3) -> list[Evidence]:
    return structural_evidence(make_case(before, after, anchor), REQUIREMENT)


def by_kind(items: list[Evidence]) -> dict[str, Evidence]:
    return {e.kind: e for e in items}


def test_real_code_change_in_target() -> None:
    after = BEFORE.replace(
        "    record = ", "    if username is None:\n        raise ValueError\n    record = "
    )

    facts = by_kind(run(BEFORE, after))

    assert facts["target_symbol"].detail == "Commented line 3 is in function `save_user`."
    assert facts["target_changed_structurally"].passed is True
    assert facts["added_condition"].detail == "Added condition `username is None`."
    assert facts["added_raise"].location is not None
    assert facts["added_raise"].location.line_start == 3
    assert facts["file_changed_structurally"].passed is True
    assert "other_symbols_changed" not in facts


def test_comment_only_change_is_not_structural() -> None:
    after = BEFORE.replace("    db.insert", "    # TODO: validate username\n    db.insert")

    facts = by_kind(run(BEFORE, after))

    assert facts["target_changed_structurally"].passed is False
    assert "Only comments, docstrings or formatting" in facts["target_changed_structurally"].detail
    assert facts["file_changed_structurally"].passed is False
    assert not any(k.startswith(("added_", "removed_")) for k in facts)


def test_change_elsewhere_is_reported_as_other_symbols() -> None:
    after = BEFORE.replace("return 1", "return 2")

    facts = by_kind(run(BEFORE, after))

    assert facts["target_changed_structurally"].passed is False
    assert facts["target_changed_structurally"].detail == "`save_user` is unchanged."
    assert "`unrelated`" in facts["other_symbols_changed"].detail
    assert facts["file_changed_structurally"].passed is True


def test_renamed_target_is_described() -> None:
    after = BEFORE.replace("def save_user", "def persist_user")

    facts = by_kind(run(BEFORE, after))

    assert "was renamed to `persist_user`" in facts["target_after"].detail
    assert facts["target_changed_structurally"].passed is True


def test_deleted_target() -> None:
    after = "def unrelated():\n    return 1\n"

    facts = by_kind(run(BEFORE, after))

    assert "no longer exists" in facts["target_after"].detail
    assert facts["target_changed_structurally"].passed is True


def test_module_level_target() -> None:
    facts = by_kind(run("import os\nX = 1\n", "import os\nX = 2\n", anchor=2))

    assert "module level" in facts["target_symbol"].detail
    assert facts["target_changed_structurally"].passed is True


def test_syntax_error_is_reported_without_failing() -> None:
    facts = by_kind(run(BEFORE, BEFORE.replace("def unrelated():", "def unrelated(:")))

    assert facts["parse_error"].passed is None
    assert "after" in facts["parse_error"].detail


def test_fact_list_is_truncated() -> None:
    calls = "".join(f"    call_{i}()\n" for i in range(MAX_FACT_EVIDENCE + 5))
    after = BEFORE.replace("    return record\n", calls + "    return record\n", 1)

    items = run(BEFORE, after)

    assert sum(e.kind == "added_call" for e in items) == MAX_FACT_EVIDENCE
    assert by_kind(items)["more_structural_changes"].detail.startswith("…and 5 more")


def test_missing_code_gives_one_neutral_item() -> None:
    (only,) = run(None, BEFORE)

    assert (only.kind, only.passed) == ("code_unavailable", None)


def test_every_item_is_located_or_explained() -> None:
    for after in (BEFORE, BEFORE.replace("return 1", "return 2"), "x = 1\n"):
        for item in run(BEFORE, after):
            assert (item.location is None) != (item.no_location_reason is None)
