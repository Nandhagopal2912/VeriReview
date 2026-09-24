import pytest

from verireview.contracts import RequirementCategory, ReviewRequirement, UtteranceType
from verireview.requirements import (
    AMBIGUITY_THRESHOLD,
    CodeContext,
    categorize,
    extract_requirements,
)

C = RequirementCategory


def categories(req: ReviewRequirement) -> list[C]:
    return [r.category for r in req.requirements]


def test_plan_section_7_example_gives_exactly_three_requirements() -> None:
    req = extract_requirements(
        "Please validate username, return HTTP 400 on invalid input, and add a test."
    )

    assert categories(req) == [C.VALIDATION, C.API_BEHAVIOR, C.TESTING]
    assert req.actionable


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        ("Rename `usr` to `username`.", [C.NAMING]),
        ("nit: `idx` -> `index`", [C.NAMING]),
        ("Add a null check for `payload`.", [C.VALIDATION]),
        ("Add a test for negative quantity.", [C.TESTING]),
        ("Handle the `DatabaseError` from the insert.", [C.ERROR_HANDLING]),
        ("Return 404 when the order is missing.", [C.API_BEHAVIOR]),
        ("Please use `pathlib` instead of `os.path`.", [C.OTHER]),
    ],
)
def test_categories(comment: str, expected: list[C]) -> None:
    assert categories(extract_requirements(comment)) == expected


@pytest.mark.parametrize(
    ("comment", "count"),
    [
        ("Rename `usr` to `user` and `pwd` to `password`.", 2),
        ("Add tests for both the `None` and the blank-name cases.", 2),
        ("Add a test for the 0 case and one for the negative case.", 2),
        ("Please handle `TimeoutError` and `ConnectionError` separately.", 2),
        ("Validate the `email` field and the `phone` field.", 2),
        ("Validate that `age` is an int and between 0 and 150.", 2),
        ("Make sure `limit` is between 1 and 100.", 1),
        ("Check `response.ok` before calling `.json()`.", 1),
        ("Catch `requests.Timeout`, retry once, and raise `FetchError` if it fails.", 3),
    ],
)
def test_coordinated_objects_are_expanded(comment: str, count: int) -> None:
    assert len(extract_requirements(comment).requirements) == count


def test_condition_clause_attaches_to_the_request() -> None:
    req = extract_requirements(
        "If the file is missing (`FileNotFoundError`) or unreadable (`PermissionError`), "
        "fall back to `DEFAULTS`."
    )

    assert [r.target for r in req.requirements] == ["FileNotFoundError", "PermissionError"]
    assert all(r.condition and r.condition.startswith("If the file") for r in req.requirements)


def test_in_clause_condition_is_extracted() -> None:
    (r,) = extract_requirements("Return HTTP 400 when `page` is not positive.").requirements

    assert r.condition == "`page` is not positive"


def test_raising_value_error_is_validation() -> None:
    assert categorize("raise `ValueError` for negative input", "raise") == C.VALIDATION
    assert categorize("raise `FetchError` if it still fails", "raise") == C.ERROR_HANDLING


@pytest.mark.parametrize(
    "comment", ["LGTM, thanks!", "Why is this sleep needed?", "Hmm, not sure."]
)
def test_comments_without_a_request_are_not_actionable(comment: str) -> None:
    req = extract_requirements(comment)

    assert not req.actionable
    assert req.ambiguity == 1.0


def test_utterance_types() -> None:
    req = extract_requirements(
        "Thanks for the fix! `usr` is too cryptic. Rename it to `user`. Maybe cache this? "
        "What happens if it fails?"
    )

    assert [u.type for u in req.utterances] == [
        UtteranceType.CHIT_CHAT,
        UtteranceType.EXPLANATION,
        UtteranceType.REQUIREMENT,
        UtteranceType.QUESTION,
        UtteranceType.QUESTION,
    ]


def test_hedged_statement_is_a_suggestion() -> None:
    (utterance,) = extract_requirements("We should probably cache this.").utterances

    assert utterance.type == UtteranceType.SUGGESTION
    assert utterance.actionable


@pytest.mark.parametrize(
    ("comment", "ambiguous"),
    [
        ("Hmm, maybe a better name here?", True),
        ("What happens if the API returns malformed JSON here?", True),
        ("This endpoint should probably be idempotent.", True),
        ("Consider renaming `data` to something more specific.", True),
        ("Could you rename `cfg` to `config`?", False),  # polite request, not a question
        ("Rename `usr` to `username`.", False),
        ("Creating a resource should return `201 Created`, not 200.", False),
    ],
)
def test_ambiguity(comment: str, ambiguous: bool) -> None:
    req = extract_requirements(comment)

    assert ((req.ambiguity or 0.0) >= AMBIGUITY_THRESHOLD) is ambiguous
    assert bool(req.ambiguity_reasons) is ((req.ambiguity or 0.0) > 0)


def test_targets_prefer_identifiers_in_the_code() -> None:
    ctx = CodeContext.from_code("def close(session):\n    session.close()\n", anchor_line=2)

    (r,) = extract_requirements("Add a `None` check for `session`.", context=ctx).requirements

    assert r.target == "session"


def test_plain_words_matched_against_code() -> None:
    ctx = CodeContext.from_code("def charge(customer_id, amount):\n    pass\n")

    (r,) = extract_requirements("Log the customer id on failure.", context=ctx).requirements

    assert r.target == "customer_id"


def test_target_symbol_from_anchor() -> None:
    ctx = CodeContext.from_code("class A:\n    def m(self):\n        return 1\n", anchor_line=3)

    assert extract_requirements("Rename it.", context=ctx).target_symbol == "A.m"


def test_suggestion_block_is_the_expected_code() -> None:
    ctx = CodeContext.from_code("def total(items):\n    tmp = 0\n    return tmp\n")

    (r,) = extract_requirements("```suggestion\n    total_price = 0\n```", context=ctx).requirements

    assert r.suggested_code == "    total_price = 0"
    assert (r.category, r.target) == (C.NAMING, "tmp")


def test_non_rename_suggestion_is_other() -> None:
    ctx = CodeContext.from_code("x = compute()\n")

    (r,) = extract_requirements(
        "```suggestion\nx = compute(cache=True)\n```", context=ctx
    ).requirements

    assert r.category == C.OTHER


def test_extraction_is_deterministic() -> None:
    comment = "Catch `requests.Timeout`, retry once, and raise `FetchError` if it still fails."

    assert extract_requirements(comment) == extract_requirements(comment)


# ---------------------------------------------------------------- Phase 10.1 (dev errors)


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        ("Log a warning when the cache misses.", [C.ERROR_HANDLING]),
        ("Please make sure the file gets closed even if parsing fails.", [C.ERROR_HANDLING]),
        ("Ignore a missing cache file instead of crashing.", [C.ERROR_HANDLING]),
        ("`bb` isn't a great name; call it `bounding_box`.", [C.NAMING]),
        ("`tmp` says nothing. Something like `normalized_email` would be better.", [C.NAMING]),
        ("We need a test for restocking an empty shelf.", [C.TESTING]),
        ("Please cover the boundary: a discount of 0.", [C.TESTING]),
        ("Make sure `amount` is actually a number.", [C.VALIDATION]),
        ("`name` can be empty here; reject it.", [C.VALIDATION]),
        ("Return an empty list instead of None when nothing matches.", [C.API_BEHAVIOR]),
        ("docstring please.", [C.OTHER]),
    ],
)
def test_phase10_1_categories(comment: str, expected: list[C]) -> None:
    assert categories(extract_requirements(comment)) == expected


def test_each_clause_keeps_its_own_category() -> None:
    req = extract_requirements("Add a test for the timeout case, and log the timeout.")
    assert categories(req) == [C.TESTING, C.ERROR_HANDLING]

    req = extract_requirements("Rename `proc` to `process` and add a docstring.")
    assert categories(req) == [C.NAMING, C.OTHER]


def test_and_that_clause_is_its_own_requirement() -> None:
    req = extract_requirements("Check that `start` is not None, and that `start <= end`.")

    assert len(req.requirements) == 2
    assert "start <= end" in req.requirements[1].description


def test_two_statuses_for_two_situations() -> None:
    req = extract_requirements("Return 400 for a missing `name` and 422 for an invalid `age`.")

    assert [r.description for r in req.requirements] == [
        "Return 400 for a missing `name`",
        "Return 422 for an invalid `age`",
    ]


def test_catch_and_return_is_one_requirement_but_log_and_reraise_are_two() -> None:
    assert len(extract_requirements("Catch `Timeout` and return an empty dict.").requirements) == 1
    assert len(extract_requirements("Log the error and re-raise it.").requirements) == 2


def test_handle_header_before_colon_is_not_a_requirement() -> None:
    req = extract_requirements("Handle the `ConnectionError` properly: log it and re-raise.")

    assert len(req.requirements) == 2
