"""Evidence: one observed fact about the code, with where it was observed.

Every item must either point at code (``location``) or say why it cannot. This is what makes
"the explanation cites actual evidence" (plan §16, §28) checkable by a test.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class EvidenceSource(StrEnum):
    DIFF = "diff"
    AST = "ast"
    RULE = "rule"
    TEST = "test"
    SEMANTIC = "semantic"


class CodeLocation(BaseModel):
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    version: str = Field(description="'before' or 'after' (fixtures), or a commit SHA.")

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        return self


class Evidence(BaseModel):
    id: str = Field(description="Unique within a result: 'E1', 'E2', ...")
    requirement_id: str | None = Field(description="None = applies to the whole case.")
    source: EvidenceSource
    kind: str = Field(description="Machine-readable fact type, e.g. 'change_near_target'.")
    passed: bool | None = Field(
        description="Supports (True) / contradicts (False) / neutral (None)."
    )
    detail: str = Field(description="Human-readable statement of the observed fact.")
    location: CodeLocation | None = None
    no_location_reason: str | None = None

    @model_validator(mode="after")
    def _located_or_explained(self) -> Self:
        if (self.location is None) == (self.no_location_reason is None):
            raise ValueError("Evidence needs exactly one of location / no_location_reason")
        return self
