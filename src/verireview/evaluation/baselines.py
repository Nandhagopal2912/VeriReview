"""Phase 6 harness: tune each similarity baseline on dev, then evaluate on dev and held-out.

Protocol (fixed before the first run):
1. fit the scorer on the dev corpus (dev comments + dev added code; TF-IDF only)
2. tune one threshold on dev to maximise 4-class accuracy (ties → the higher, more
   conservative threshold)
3. evaluate dev and held-out with that frozen threshold through the same ``evaluate()`` as
   the rule pipelines

Added after the first run (reported separately, labelled as such): the accuracy criterion
collapsed every baseline to "always NOT_SATISFIED", the majority class, which says nothing about
whether the scores carry signal. So we also report
- ROC-AUC: does a valid resolution (gold SATISFIED) score higher than an invalid one (gold
  NOT / PARTIALLY)? 0.5 = no signal. UNCERTAIN cases are left out.
- a balanced operating point: the dev threshold maximising Youden's J (TPR - FPR) on the same
  valid-vs-invalid split, evaluated on held-out unchanged.
"""

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from verireview.contracts import Verdict
from verireview.dataset import Fixture
from verireview.evaluation.runner import EvaluationReport, evaluate
from verireview.semantic import Scorer, SimilarityVerifier, change_text, comment_text


class BaselineResult(BaseModel):
    scorer: str
    config: dict[str, Any]
    threshold: float  # pre-specified criterion: dev 4-class accuracy
    dev: EvaluationReport
    heldout: EvaluationReport
    youden_threshold: float  # added after the first run: dev Youden's J (valid vs invalid)
    dev_youden: EvaluationReport
    heldout_youden: EvaluationReport
    auc_dev: float | None
    auc_heldout: float | None
    scores: dict[str, float]  # case_id → similarity (dev and held-out)


class BaselineReport(BaseModel):
    commit: str
    results: list[BaselineResult]


def tune_threshold(scores: Sequence[float], gold: Sequence[Verdict]) -> float:
    """Threshold maximising accuracy of (score ≥ t → SATISFIED, else NOT_SATISFIED)."""
    ordered = sorted(set(scores))
    candidates = [0.0, *[(a + b) / 2 for a, b in zip(ordered, ordered[1:], strict=False)]]
    candidates.append((ordered[-1] + 1e-6) if ordered else 1.0)

    def accuracy(t: float) -> int:
        return sum(
            (Verdict.SATISFIED if s >= t else Verdict.NOT_SATISFIED) == g
            for s, g in zip(scores, gold, strict=True)
        )

    best = max(accuracy(t) for t in candidates)
    return max(t for t in candidates if accuracy(t) == best)


def run_baseline(
    scorer: Scorer,
    dev: Sequence[Fixture],
    heldout: Sequence[Fixture],
    dev_root: Path,
    heldout_root: Path,
) -> BaselineResult:
    corpus = [comment_text(f.case) for f in dev] + [change_text(f.case) for f in dev]
    scorer.fit(corpus)
    probe = SimilarityVerifier(scorer, threshold=0.0)
    dev_scores = {f.meta.case_id: probe.score(f.case) for f in dev}
    heldout_scores = {f.meta.case_id: probe.score(f.case) for f in heldout}

    dev_s = [dev_scores[f.meta.case_id] for f in dev]
    dev_gold = [f.meta.expected_verdict for f in dev]
    held_s = [heldout_scores[f.meta.case_id] for f in heldout]
    held_gold = [f.meta.expected_verdict for f in heldout]

    threshold = tune_threshold(dev_s, dev_gold)
    youden = tune_threshold_youden(dev_s, dev_gold)
    verifier, balanced = SimilarityVerifier(scorer, threshold), SimilarityVerifier(scorer, youden)
    return BaselineResult(
        scorer=scorer.name,
        config=scorer.describe(),
        threshold=threshold,
        dev=evaluate(verifier, dev, dev_root),
        heldout=evaluate(verifier, heldout, heldout_root),
        youden_threshold=youden,
        dev_youden=evaluate(balanced, dev, dev_root),
        heldout_youden=evaluate(balanced, heldout, heldout_root),
        auc_dev=roc_auc(dev_s, dev_gold),
        auc_heldout=roc_auc(held_s, held_gold),
        scores={**dev_scores, **heldout_scores},
    )


_VALID = {Verdict.SATISFIED}
_INVALID = {Verdict.NOT_SATISFIED, Verdict.PARTIALLY_SATISFIED}


def roc_auc(scores: Sequence[float], gold: Sequence[Verdict]) -> float | None:
    """P(valid resolution scores higher than invalid one), ties count 1/2 (Mann-Whitney U)."""
    pos = [s for s, g in zip(scores, gold, strict=True) if g in _VALID]
    neg = [s for s, g in zip(scores, gold, strict=True) if g in _INVALID]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def tune_threshold_youden(scores: Sequence[float], gold: Sequence[Verdict]) -> float:
    """Threshold maximising TPR - FPR for valid (SATISFIED) vs invalid (NOT / PARTIAL)."""
    pairs = [(s, g in _VALID) for s, g in zip(scores, gold, strict=True) if g in _VALID | _INVALID]
    positives = sum(valid for _, valid in pairs)
    negatives = len(pairs) - positives
    if not positives or not negatives:
        return 0.5
    ordered = sorted({s for s, _ in pairs})
    candidates = [(a + b) / 2 for a, b in zip(ordered, ordered[1:], strict=False)] or ordered

    def j(t: float) -> float:
        tpr = sum(valid and s >= t for s, valid in pairs) / positives
        fpr = sum((not valid) and s >= t for s, valid in pairs) / negatives
        return tpr - fpr

    best = max(j(t) for t in candidates)
    return max(t for t in candidates if j(t) == best)


def current_commit() -> str:
    """The checked-out git commit, for reproducibility ('unknown' outside a repository)."""
    try:
        out = subprocess.run(  # noqa: S603 - fixed argument list, no user input
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - git from PATH is intended
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip()
