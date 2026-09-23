"""ReviewRequirement: what the reviewer actually asked for, as atomic, checkable requirements."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

REQUIREMENT_SCHEMA_VERSION = "1"


class RequirementCategory(StrEnum):
    """MVP categories (plan §8); ``OTHER`` until extraction can classify (Phase 4)."""

    NAMING = "naming"
    VALIDATION = "validation"
    TESTING = "testing"
    ERROR_HANDLING = "error_handling"
    API_BEHAVIOR = "api_behavior"
    OTHER = "other"


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


class ReviewRequirement(BaseModel):
    schema_version: str = REQUIREMENT_SCHEMA_VERSION
    case_id: str
    target_file: str
    target_symbol: str | None = None
    requirements: list[Requirement] = Field(min_length=1)
    ambiguity: float | None = Field(default=None, ge=0.0, le=1.0)
    source: Literal["manual", "extracted", "stub"] = Field(
        description="manual = gold annotation; extracted = automatic (Phase 4); stub = placeholder."
    )
