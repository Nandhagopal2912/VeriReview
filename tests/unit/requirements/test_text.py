import pytest

from verireview.requirements.text import (
    leading_verb,
    mask,
    prepare,
    split_clauses,
    split_sentences,
    strip_fillers,
)


def sentences(text: str) -> list[str]:
    masked = mask(text)
    return [masked.restore(s) for s in split_sentences(masked)]


def clauses(text: str) -> list[str]:
    masked = mask(text)
    return [masked.restore(c) for c in split_clauses(masked.text)]


def test_prepare_extracts_suggestions_and_drops_noise() -> None:
    comment = (
        "> quoted reviewer text\n"
        "See ![img](https://x/y.png) and <img src='a'/> https://example.com\n"
        "```suggestion\n    total = 0\n```\n"
        "```python\nprint('ignored')\n```\n"
        "- Rename it"
    )

    prepared = prepare(comment)

    assert prepared.suggestions == ("    total = 0",)
    assert "quoted" not in prepared.text
    assert "print" not in prepared.text
    assert "https" not in prepared.text and "<img" not in prepared.text
    assert prepared.text.endswith("Rename it")


def test_mask_restores_exactly() -> None:
    text = "Call `a.b()` (e.g. twice) then `c`."
    masked = mask(text)

    assert "`" not in masked.text and "(" not in masked.text
    assert masked.restore(masked.text) == text


def test_sentences_do_not_break_inside_code_or_abbreviations() -> None:
    assert sentences("Check `response.ok` before `.json()`. Then e.g. retry. Done!") == [
        "Check `response.ok` before `.json()`.",
        "Then e.g. retry.",
        "Done!",
    ]


def test_sentences_split_on_lines() -> None:
    assert sentences("Add a test\nRename `x`") == ["Add a test", "Rename `x`"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Catch `requests.Timeout`, retry once, and raise `FetchError` if it still fails.",
            ["Catch `requests.Timeout`", "retry once", "and raise `FetchError` if it still fails."],
        ),
        (
            "Validate that `age` is between 0 and 150.",
            ["Validate that `age` is between 0 and 150."],
        ),
        (
            "Please log the failure (with the id) before re-raising, we have no trace of these.",
            ["Please log the failure (with the id) before re-raising, we have no trace of these."],
        ),
        (
            "`get_user` should raise `UserNotFound`, not return None.",
            ["`get_user` should raise `UserNotFound`, not return None."],
        ),
        (
            "This crashes when `count` is 0; handle that case.",
            ["This crashes when `count` is 0", "handle that case."],
        ),
        (
            "Validate `username` (non-empty, max 32 chars) and return HTTP 400.",
            # " and " is itself the delimiter here, so it is not part of either clause.
            ["Validate `username` (non-empty, max 32 chars)", "return HTTP 400."],
        ),
    ],
)
def test_clauses_split_only_before_request_verbs(text: str, expected: list[str]) -> None:
    assert clauses(text) == expected


@pytest.mark.parametrize(
    ("clause", "verb"),
    [
        ("Please add a test", "add"),
        ("and then rename it", "rename"),
        ("Could you please validate this?", "validate"),
        ("Don't swallow the exception", "swallow"),
        ("Consider renaming `data`", "rename"),
        ("Consider splitting this", "split"),
        ("Consider this carefully", None),
        ("we have no trace", None),
        ("", None),
    ],
)
def test_leading_verb(clause: str, verb: str | None) -> None:
    assert leading_verb(clause) == verb


def test_strip_fillers() -> None:
    assert strip_fillers("and please add a test.") == "add a test"
