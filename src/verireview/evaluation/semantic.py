"""Phase 7: evaluate the code model's relevance evidence.

Two questions, on dev and held-out:
1. Does adding the evidence change any verdict? It must not: the evidence is neutral and the
   aggregator is the MVP's. ``verdict_changes`` counts differences from ``mvp`` (expected 0).
2. Does it carry signal? Per case, take the *weakest* requirement's best-chunk relevance (every
   requirement must be addressed; no added code scores 0) and compute ROC-AUC of valid
   (gold SATISFIED) vs invalid (gold NOT / PARTIALLY) resolutions, as in Phase 6. To show what
   using it as a decision would cost, ``operating_point`` applies a dev-tuned threshold
   (Youden's J) unchanged to held-out.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from verireview.contracts import Verdict
from verireview.dataset import Fixture
from verireview.evaluation.baselines import roc_auc, tune_threshold_youden
from verireview.evaluation.runner import dataset_hash
from verireview.evidence.semantic import requirement_relevance
from verireview.semantic import Encoder, UniXcoderEncoder
from verireview.verification import mvp_pipeline, semantic_pipeline


class CaseRelevance(BaseModel):
    case_id: str
    gold: Verdict
    mvp: Verdict
    phase7: Verdict
    scores: dict[str, float]  # requirement id → best-chunk relevance (extracted requirements)
    case_score: float  # weakest requirement; 0.0 when no code was added


class SemanticEvidenceReport(BaseModel):
    name: str
    dataset_hash: str
    model: dict[str, Any]
    n: int
    verdict_changes: int
    auc: float | None
    cases: list[CaseRelevance]


def evaluate_semantic_evidence(
    name: str, fixtures: Sequence[Fixture], root: Path, encoder: Encoder
) -> SemanticEvidenceReport:
    rules, semantic = mvp_pipeline(), semantic_pipeline(encoder)
    cases = []
    for fixture in fixtures:
        case = fixture.case
        requirement = semantic.requirement_stage(case)
        scores = {
            r.requirement_id: r.score for r in requirement_relevance(case, requirement, encoder)
        }
        cases.append(
            CaseRelevance(
                case_id=fixture.meta.case_id,
                gold=fixture.meta.expected_verdict,
                mvp=rules.run(case).verdict,
                phase7=semantic.run(case).verdict,
                scores=scores,
                case_score=min(scores.values(), default=0.0),
            )
        )
    return SemanticEvidenceReport(
        name=name,
        dataset_hash=dataset_hash(root),
        model=encoder.describe() if isinstance(encoder, UniXcoderEncoder) else {},
        n=len(cases),
        verdict_changes=sum(c.mvp != c.phase7 for c in cases),
        auc=roc_auc([c.case_score for c in cases], [c.gold for c in cases]),
        cases=cases,
    )


def youden_threshold(report: SemanticEvidenceReport) -> float:
    return tune_threshold_youden(
        [c.case_score for c in report.cases], [c.gold for c in report.cases]
    )


def operating_point(
    report: SemanticEvidenceReport, threshold: float
) -> tuple[float | None, float | None]:
    """(false acceptance, false blocking) if 'relevance ≥ threshold' meant SATISFIED."""
    invalid = [
        c for c in report.cases if c.gold in (Verdict.NOT_SATISFIED, Verdict.PARTIALLY_SATISFIED)
    ]
    valid = [c for c in report.cases if c.gold == Verdict.SATISFIED]
    far = sum(c.case_score >= threshold for c in invalid) / len(invalid) if invalid else None
    fbr = sum(c.case_score < threshold for c in valid) / len(valid) if valid else None
    return far, fbr
