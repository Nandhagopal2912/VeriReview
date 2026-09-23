"""Core data contracts: ReviewCase, ReviewRequirement, Evidence, VerificationResult."""

from verireview.contracts.evidence import CodeLocation, Evidence, EvidenceSource
from verireview.contracts.requirement import (
    Requirement,
    RequirementCategory,
    ReviewRequirement,
    Utterance,
    UtteranceType,
)
from verireview.contracts.review_case import (
    SCHEMA_VERSION,
    ChangedFile,
    CommitRef,
    ResolutionWindow,
    ReviewCase,
    ReviewThread,
    ThreadComment,
    WindowFlag,
)
from verireview.contracts.verification import (
    Confidence,
    RequirementStatus,
    Verdict,
    VerificationResult,
)

__all__ = [
    "SCHEMA_VERSION",
    "ChangedFile",
    "CodeLocation",
    "CommitRef",
    "Confidence",
    "Evidence",
    "EvidenceSource",
    "Requirement",
    "RequirementCategory",
    "RequirementStatus",
    "ResolutionWindow",
    "ReviewCase",
    "ReviewRequirement",
    "ReviewThread",
    "ThreadComment",
    "Utterance",
    "UtteranceType",
    "Verdict",
    "VerificationResult",
    "WindowFlag",
]
