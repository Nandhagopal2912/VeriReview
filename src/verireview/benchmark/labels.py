"""Annotation labels (docs/annotation_guide.md): one annotator's judgement of one case.

The verdict is not chosen freely: it is derived from the per-requirement statuses and the
ambiguity flag (guide §5), so labels cannot contradict themselves.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verireview.contracts import RequirementCategory, Verdict


class Status(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNCERTAIN = "uncertain"


class ExclusionReason(StrEnum):
    NO_REQUIREMENT = "no_requirement"
    NOT_PYTHON_CODE = "not_python_code"
    WINDOW_UNUSABLE = "window_unusable"
    REQUIRES_EXTERNAL_CONTEXT = "requires_external_context"
    BOT_OR_AUTOMATED = "bot_or_automated"


class RequirementLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RequirementCategory
    description: str = Field(min_length=3)
    status: Status


class CaseAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    include: bool
    exclusion_reason: ExclusionReason | None = None
    requirements: list[RequirementLabel] = Field(default_factory=list)
    ambiguous: bool = False
    verdict: Verdict | None = None
    evidence: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    notes: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.include:
            if self.exclusion_reason is None:
                raise ValueError(f"{self.case_id}: an excluded case needs exclusion_reason")
            return self
        if self.exclusion_reason is not None:
            raise ValueError(f"{self.case_id}: an included case has no exclusion_reason")
        if not self.requirements:
            raise ValueError(f"{self.case_id}: an included case needs at least one requirement")
        derived = derive_verdict([r.status for r in self.requirements], self.ambiguous)
        if self.verdict is None:
            self.verdict = derived
        elif self.verdict != derived:
            raise ValueError(
                f"{self.case_id}: verdict {self.verdict} contradicts the statuses ({derived})"
            )
        return self

    @property
    def category(self) -> RequirementCategory | None:
        return self.requirements[0].category if self.requirements else None


class AnnotationFile(BaseModel):
    """What the annotation page exports: one annotator, one batch of cases."""

    model_config = ConfigDict(extra="forbid")

    annotator: str = Field(min_length=1)
    batch: str
    sheet_version: str
    annotations: list[CaseAnnotation]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        ids = [a.case_id for a in self.annotations]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"cases annotated twice: {duplicates}")
        return self

    def by_case(self) -> dict[str, CaseAnnotation]:
        return {a.case_id: a for a in self.annotations}


def derive_verdict(statuses: list[Status], ambiguous: bool) -> Verdict:
    """Guide §5, first matching row wins."""
    if ambiguous:
        return Verdict.UNCERTAIN
    found = set(statuses)
    if Status.SATISFIED in found and Status.NOT_SATISFIED in found:
        return Verdict.PARTIALLY_SATISFIED
    if Status.NOT_SATISFIED in found:
        return Verdict.NOT_SATISFIED
    if Status.UNCERTAIN in found:
        return Verdict.UNCERTAIN
    return Verdict.SATISFIED
