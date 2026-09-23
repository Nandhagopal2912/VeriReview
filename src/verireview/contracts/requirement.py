"""ReviewRequirement: what the reviewer actually asked for, as atomic, checkable requirements."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# v2 (Phase 4): suggested_code, actionable, ambiguity_reasons, utterances.
REQUIREMENT_SCHEMA_VERSION = "2"


class RequirementCategory(StrEnum):
    """MVP categories (plan §8); ``OTHER`` for everything else (docs, style, refactoring…)."""

    NAMING = "naming"
    VALIDATION = "validation"
    TESTING = "testing"
    ERROR_HANDLING = "error_handling"
    API_BEHAVIOR = "api_behavior"
    OTHER = "other"


class UtteranceType(StrEnum):
    """What a sentence of the comment is doing (plan §7)."""

    REQUIREMENT = "requirement"  # a request for a change
    SUGGESTION = "suggestion"  # a hedged request ("maybe", "consider", "probably")
    QUESTION = "question"  # asks something; may imply a request ("what happens if…?")
    EXPLANATION = "explanation"  # rationale or context, nothing to verify
    CHIT_CHAT = "chit_chat"  # "LGTM", "thanks"


class Utterance(BaseModel):
    text: str
    type: UtteranceType
    actionable: bool


class Requirement(BaseModel):
    id: str = Field(description="Stable within a case: 'R1', 'R2', ...")
    category: RequirementCategory
    description: str = Field(description="The requirement in plain words.")
    target: str | None = Field(
        default=None, description="Identifier/symbol the requirement is about."
    )
    condition: str | None = Field(
        default=None, description="When it applies, e.g. 'username is None'."
    )
    expected_behavior: str | None = Field(default=None, description="What must happen.")
    suggested_code: str | None = Field(
        default=None, description="Exact replacement code from a GitHub ```suggestion block."
    )


class ReviewRequirement(BaseModel):
    schema_version: str = REQUIREMENT_SCHEMA_VERSION
    case_id: str
    target_file: str
    target_symbol: str | None = None
    requirements: list[Requirement] = Field(min_length=1)
    actionable: bool = Field(
        default=True,
        description="False when the comment asks for nothing (e.g. 'LGTM'); `requirements` then "
        "holds a single placeholder and ambiguity is 1.0.",
    )
    ambiguity: float | None = Field(default=None, ge=0.0, le=1.0)
    ambiguity_reasons: list[str] = Field(default_factory=list)
    utterances: list[Utterance] = Field(default_factory=list)
    source: Literal["manual", "extracted", "stub"] = Field(
        description="manual = gold annotation; extracted = automatic (Phase 4); stub = placeholder."
    )
