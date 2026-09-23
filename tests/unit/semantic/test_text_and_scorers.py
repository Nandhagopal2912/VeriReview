import numpy as np
import pytest

from helpers.cases import make_case
from verireview.contracts import Verdict
from verireview.semantic import (
    EmbeddingScorer,
    LexicalScorer,
    SimilarityVerifier,
    TfidfScorer,
    change_text,
    comment_text,
    words,
)

BEFORE = "def save(db, username):\n    db.insert(username)\n"
AFTER = (
    "def save(db, username):\n"
    "    # validate the username\n"
    "    if username is None:\n"
    "        raise ValueError('username required')\n"
    "    db.insert(username)\n"
)


def case(comment: str = "Validate `username` before saving.", after: str = AFTER, **kw: object):
    from verireview.ingestion import make_unified_diff

    base = make_case(BEFORE, after, 2)
    return base.model_copy(
        update={
            "unified_diff": make_unified_diff(BEFORE, after, "m.py", "m.py"),
            "thread": base.thread.model_copy(
                update={"comments": [base.thread.comments[0].model_copy(update={"body": comment})]}
            ),
            **kw,
        }
    )


# ---------------------------------------------------------------- text


def test_words_split_identifiers_and_drop_stopwords() -> None:
    assert words("Rename `total_price` to getUserName, please") == [
        "rename",
        "total",
        "price",
        "get",
        "user",
        "name",
    ]
    assert words("return HTTP 400") == ["http", "400"]


def test_comment_text_is_cleaned() -> None:
    c = case("> quoted\nAdd a check. See https://example.com\n```python\nx = 1\n```")

    assert comment_text(c) == "Add a check. See"


def test_change_text_holds_only_added_lines_including_comments() -> None:
    text = change_text(case())

    assert "# validate the username" in text  # comments are kept on purpose
    assert "raise ValueError" in text
    assert "def save" not in text  # unchanged lines are not "added"


def test_change_text_includes_new_test_lines() -> None:
    c = case(
        test_files={"tests/t.py": "def test_a():\n    pass\n\ndef test_b():\n    save(None)\n"},
        test_files_before={"tests/t.py": "def test_a():\n    pass\n"},
    )

    assert "def test_b():" in change_text(c)
    assert "def test_a():" not in change_text(c)


def test_no_change_gives_empty_text() -> None:
    assert change_text(case(after=BEFORE)) == ""


# ---------------------------------------------------------------- scorers


def test_lexical_is_share_of_comment_words_present() -> None:
    scorer = LexicalScorer()

    assert scorer.score("validate username", "if not username: validate()") == 1.0
    assert scorer.score("validate username", "print(username)") == 0.5
    assert scorer.score("validate username", "") == 0.0


def test_tfidf_needs_fitting_and_is_bounded() -> None:
    scorer = TfidfScorer()
    with pytest.raises(RuntimeError, match="fit"):
        scorer.score("a", "b")

    scorer.fit(["validate username", "log the error", "rename total price"])

    assert scorer.score("validate username", "validate username") == pytest.approx(1.0)
    assert scorer.score("validate username", "log the error") == 0.0
    assert 0.0 < scorer.score("validate username", "username") < 1.0


def test_embedding_scorer_uses_cosine_of_the_encoder() -> None:
    vectors = {"a": np.array([1.0, 0.0]), "b": np.array([1.0, 1.0]), "c": np.array([0.0, 1.0])}
    scorer = EmbeddingScorer(encoder=lambda texts: [vectors[t] for t in texts])

    assert scorer.score("a", "a") == pytest.approx(1.0)
    assert scorer.score("a", "b") == pytest.approx(2**-0.5)
    assert scorer.score("a", "c") == pytest.approx(0.0)
    assert scorer.score("a", "  ") == 0.0  # no added code, no encoding needed


# ---------------------------------------------------------------- verifier


def test_verifier_thresholds_the_similarity_and_cites_it() -> None:
    lenient, strict = (
        SimilarityVerifier(LexicalScorer(), 0.1),
        SimilarityVerifier(LexicalScorer(), 1.1),
    )

    assert lenient.run(case()).verdict == Verdict.SATISFIED
    result = strict.run(case())
    assert result.verdict == Verdict.NOT_SATISFIED
    assert result.evidence[0].kind == "semantic_similarity"
    assert "threshold 1.100" in result.evidence[0].detail
    assert result.pipeline_version == "baseline-lexical-1"


def test_verifier_rejects_when_nothing_was_added() -> None:
    assert SimilarityVerifier(LexicalScorer(), 0.0).run(case(after=BEFORE)).verdict == (
        Verdict.NOT_SATISFIED
    )


def test_baseline_is_fooled_by_a_comment_mentioning_the_fix() -> None:
    """The weakness the ablation study measures: comments count as 'added code'."""
    comment_only = BEFORE.replace("    db.insert", "    # TODO: validate username\n    db.insert")
    verifier = SimilarityVerifier(LexicalScorer(), 0.5)

    # "validate", "username" of {validate, username, before, saving}: half the words, no check.
    assert verifier.score(case(after=comment_only)) == pytest.approx(2 / 4)
    assert verifier.run(case(after=comment_only)).verdict == Verdict.SATISFIED


@pytest.mark.model
def test_real_embedding_model_ranks_a_paraphrase_above_unrelated_text() -> None:
    scorer = EmbeddingScorer()

    related = scorer.score("Check that the username is not empty", "if not username: raise")
    unrelated = scorer.score("Check that the username is not empty", "plot.set_title('Sales')")

    assert related > unrelated
