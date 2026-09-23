"""Verification pipeline: requirement stage → evidence stages → aggregator (plan §2).

Stages are plain callables so later phases swap them in without rewiring:
Phase 4 replaces the requirement stage, Phases 3/5/6/7 add evidence stages, and Phase 8
replaces the aggregator. The pipeline itself owns evidence numbering and the explanation, so
every result is built the same way.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from verireview.contracts import (
    Confidence,
    Evidence,
    RequirementStatus,
    ReviewCase,
    ReviewRequirement,
    Verdict,
    VerificationResult,
)
from verireview.explanations import render_explanation


class RequirementStage(Protocol):
    def __call__(self, case: ReviewCase) -> ReviewRequirement: ...


class EvidenceStage(Protocol):
    """Returns evidence items; their ``id`` is a placeholder the pipeline replaces."""

    def __call__(self, case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]: ...


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    confidence: Confidence
    per_requirement: list[RequirementStatus]
    notes: list[str] = field(default_factory=list)


class Aggregator(Protocol):
    def __call__(
        self, case: ReviewCase, requirement: ReviewRequirement, evidence: list[Evidence]
    ) -> Decision: ...


@dataclass(frozen=True)
class Pipeline:
    version: str
    requirement_stage: RequirementStage
    evidence_stages: Sequence[EvidenceStage]
    aggregator: Aggregator

    def run(self, case: ReviewCase) -> VerificationResult:
        requirement = self.requirement_stage(case)
        drafts = [item for stage in self.evidence_stages for item in stage(case, requirement)]
        evidence = [e.model_copy(update={"id": f"E{i}"}) for i, e in enumerate(drafts, start=1)]
        decision = self.aggregator(case, requirement, evidence)
        return VerificationResult(
            case_id=case.case_id,
            verdict=decision.verdict,
            confidence=decision.confidence,
            per_requirement=decision.per_requirement,
            evidence=evidence,
            explanation=render_explanation(
                case, requirement, evidence, decision.verdict, decision.confidence, decision.notes
            ),
            pipeline_version=self.version,
        )
