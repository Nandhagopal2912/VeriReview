"""Phase 7 code-aware model: UniXcoder (`microsoft/unixcoder-base`), zero-shot, on CPU.

Why UniXcoder (roadmap D7): it was pre-trained with contrastive text↔code objectives, so the
cosine of its embeddings measures comment↔code relevance without fine-tuning. The dataset is far
too small to fine-tune anything. CodeBERT's raw embeddings are not trained for text↔code
similarity.

Encoding follows the model's reference implementation (`unixcoder.py`, encoder-only mode):
``<s> <encoder-only> </s> tokens </s>``, truncated to 512 tokens, mean pooling over the tokens,
L2-normalised. The model revision is pinned, so scores are reproducible.

torch / transformers / numpy come from the optional `nlp` group and are imported lazily.
"""

from functools import lru_cache
from typing import Any

from verireview.semantic.scorers import EmbeddingScorer, Encoder

DEFAULT_CODE_MODEL = "microsoft/unixcoder-base"
DEFAULT_CODE_MODEL_REVISION = "5604afdc964f6c53782a6813140ade5216b99006"  # pinned: reproducible
MAX_TOKENS = 512
_MODE = "<encoder-only>"


class UniXcoderEncoder:
    """texts → L2-normalised embeddings, shape (n, 768). Loads the model on first use; caches."""

    def __init__(
        self,
        model: str = DEFAULT_CODE_MODEL,
        revision: str = DEFAULT_CODE_MODEL_REVISION,
        batch_size: int = 16,
    ) -> None:
        self.model = model
        self.revision = revision
        self.batch_size = batch_size
        self._tokenizer: Any = None
        self._model: Any = None
        self._cache: dict[str, Any] = {}
        self.truncated = 0  # texts cut at MAX_TOKENS (reported, since it hides code)

    def __call__(self, texts: list[str]) -> Any:
        import numpy as np

        missing = list(dict.fromkeys(t for t in texts if t not in self._cache))
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start : start + self.batch_size]
            for text, vector in zip(batch, self._encode(batch), strict=True):
                self._cache[text] = vector
        return np.stack([self._cache[t] for t in texts])

    def describe(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "revision": self.revision,
            "device": "cpu",
            "pooling": "mean, L2-normalised",
            "max_tokens": MAX_TOKENS,
            "texts_truncated": self.truncated,
        }

    def _encode(self, texts: list[str]) -> Any:
        import torch

        tokenizer, model = self._load()
        ids = [self._ids(t) for t in texts]
        width = max(len(i) for i in ids)
        pad = tokenizer.pad_token_id
        input_ids = torch.tensor([i + [pad] * (width - len(i)) for i in ids])
        mask = input_ids.ne(pad)
        with torch.inference_mode():
            tokens = model(input_ids=input_ids, attention_mask=mask.long())[0]
        pooled = (tokens * mask.unsqueeze(-1)).sum(1) / mask.sum(-1).unsqueeze(-1)
        return torch.nn.functional.normalize(pooled, p=2, dim=1).numpy()

    def _ids(self, text: str) -> list[int]:
        tokenizer = self._tokenizer
        tokens = tokenizer.tokenize(text)
        if len(tokens) > MAX_TOKENS - 4:
            self.truncated += 1
            tokens = tokens[: MAX_TOKENS - 4]
        wrapped = [tokenizer.cls_token, _MODE, tokenizer.sep_token, *tokens, tokenizer.sep_token]
        return list(tokenizer.convert_tokens_to_ids(wrapped))

    def _load(self) -> tuple[Any, Any]:
        if self._model is None:
            from transformers import AutoModel, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model, revision=self.revision)
            self._model = AutoModel.from_pretrained(self.model, revision=self.revision)
            self._model.eval()
        return self._tokenizer, self._model


@lru_cache(maxsize=1)
def default_code_encoder() -> UniXcoderEncoder:
    """One shared encoder per process (loading the model takes seconds)."""
    return UniXcoderEncoder()


class CodeModelScorer(EmbeddingScorer):
    """Plan §13, baseline 4: cosine of UniXcoder embeddings of the comment and the change."""

    name = "unixcoder"

    def __init__(self, encoder: Encoder | None = None) -> None:
        super().__init__(DEFAULT_CODE_MODEL, encoder or default_code_encoder())

    def describe(self) -> dict[str, Any]:
        encoder = self._encoder
        details = encoder.describe() if isinstance(encoder, UniXcoderEncoder) else {}
        return {"scorer": self.name, **details}
