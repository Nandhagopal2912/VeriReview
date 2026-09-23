"""VerificationResult: verdict + confidence level + the evidence behind it (plan §4, §15, §16)."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from verireview.contracts.evidence import Evidence

RESULT_SCHEMA_VERSION = "1"


class Verdict(StrEnum):
    SATISFIED = "SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNCERTAIN = "UNCERTAIN"


class Confidence(StrEnum):
    """Coarse levels only: numeric probabilities need calibration first (plan §15)."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RequirementStatus(BaseModel):
    requirement_id: str
    status: Verdict
    evidence_ids: list[str]


class VerificationResult(BaseModel):
    schema_version: str = RESULT_SCHEMA_VERSION
    case_id: str
    verdict: Verdict
    confidence: Confidence
    per_requirement: list[RequirementStatus]
    evidence: list[Evidence]
    explanation: str
    pipeline_version: str = Field(description="Identifies the exact pipeline for reproducibility.")

    @model_validator(mode="after")
    def _references_resolve(self) -> Self:
        ids = [e.id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence ids must be unique")
        known = set(ids)
        for status in self.per_requirement:
            missing = set(status.evidence_ids) - known
            if missing:
                raise ValueError(f"Requirement {status.requirement_id} cites unknown {missing}")
        return self
