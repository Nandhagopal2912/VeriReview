"""A similarity baseline as a verifier with the same interface as a Pipeline.

Decision: no added code → NOT_SATISFIED; else SATISFIED when similarity ≥ threshold,
NOT_SATISFIED otherwise. It never says PARTIALLY_SATISFIED or UNCERTAIN: one similarity number
cannot express "half done" or "unclear". That limitation is part of what the baseline measures.
"""

from dataclasses import dataclass

from verireview.contracts import (
    Confidence,
    Evidence,
    EvidenceSource,
    RequirementStatus,
    ReviewCase,
    ReviewRequirement,
    Verdict,
    VerificationResult,
)
from verireview.semantic.scorers import Scorer
from verireview.semantic.text import change_text, comment_text


@dataclass
class SimilarityVerifier:
    scorer: Scorer
    threshold: float

    @property
    def version(self) -> str:
        return f"baseline-{self.scorer.name}-1"

    def score(self, case: ReviewCase) -> float:
        return self.scorer.score(comment_text(case), change_text(case))

    def run(
        self, case: ReviewCase, requirement: ReviewRequirement | None = None
    ) -> VerificationResult:
        change = change_text(case)
        if not change.strip():
            # Explicit, not via the score: a threshold of 0 must not accept "nothing added".
            passed, detail = False, "No code was added after the comment."
        else:
            similarity = self.scorer.score(comment_text(case), change)
            passed = similarity >= self.threshold
            detail = (
                f"{self.scorer.name} similarity between the comment and the added code: "
                f"{similarity:.3f} (threshold {self.threshold:.3f})."
            )
        verdict = Verdict.SATISFIED if passed else Verdict.NOT_SATISFIED
        evidence = Evidence(
            id="E1",
            requirement_id=None,
            source=EvidenceSource.SEMANTIC,
            kind="semantic_similarity",
            passed=passed,
            detail=detail,
            no_location_reason="compares the whole comment with all added lines",
        )
        return VerificationResult(
            case_id=case.case_id,
            verdict=verdict,
            confidence=Confidence.LOW,
            per_requirement=[
                RequirementStatus(requirement_id="R1", status=verdict, evidence_ids=["E1"])
            ],
            evidence=[evidence],
            explanation=f"{evidence.detail}\nResult: {verdict.value} (similarity baseline).",
            pipeline_version=self.version,
        )
