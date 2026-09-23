from typing import Any

import numpy as np
import pytest

from helpers.semantic import fake_encoder
from verireview.semantic import (
    DEFAULT_CODE_MODEL,
    DEFAULT_CODE_MODEL_REVISION,
    CodeModelScorer,
    UniXcoderEncoder,
)
from verireview.semantic.code_model import MAX_TOKENS


class FakeTokenizer:
    cls_token, sep_token, pad_token_id = "<s>", "</s>", 1

    def tokenize(self, text: str) -> list[str]:
        return text.split()

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        return [len(t) for t in tokens]


def test_scorer_is_the_cosine_of_the_encoder() -> None:
    scorer = CodeModelScorer(encoder=fake_encoder)

    assert scorer.name == "unixcoder"
    assert scorer.score("validate username", "validate(username)") == pytest.approx(1.0)
    assert scorer.score("validate username", "plot(sales)") == pytest.approx(0.0)
    assert scorer.score("validate username", "") == 0.0


def test_the_model_revision_is_pinned_to_a_commit() -> None:
    assert DEFAULT_CODE_MODEL == "microsoft/unixcoder-base"
    assert len(DEFAULT_CODE_MODEL_REVISION) == 40  # a commit hash, not a moving branch
    assert UniXcoderEncoder().describe()["revision"] == DEFAULT_CODE_MODEL_REVISION


def test_input_follows_the_encoder_only_format_and_is_truncated() -> None:
    encoder = UniXcoderEncoder()
    encoder._tokenizer = FakeTokenizer()

    assert encoder._ids("ab c") == [3, 14, 4, 2, 1, 4]  # <s> <encoder-only> </s> ab c </s>
    assert len(encoder._ids("x " * 1000)) == MAX_TOKENS
    assert encoder.truncated == 1


def test_each_text_is_encoded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    encoder = UniXcoderEncoder(batch_size=2)
    calls: list[list[str]] = []

    def encode(texts: list[str]) -> Any:
        calls.append(texts)
        return fake_encoder(texts)

    monkeypatch.setattr(encoder, "_encode", encode)

    first = encoder(["a", "b", "c", "a"])
    second = encoder(["c", "b"])

    assert calls == [["a", "b"], ["c"]]
    assert first.shape == (4, 64)
    np.testing.assert_array_equal(second[0], first[2])


@pytest.mark.model
def test_real_code_model_links_a_request_to_the_code_that_does_it() -> None:
    scorer = CodeModelScorer()
    request = "Check that the username is not empty before saving"

    matching = scorer.score(request, "if not username:\n    raise ValueError('username required')")
    unrelated = scorer.score(request, "plot.set_title('Sales')")

    assert matching > unrelated
    assert scorer.describe()["revision"] == DEFAULT_CODE_MODEL_REVISION
