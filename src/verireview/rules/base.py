"""Common rule machinery: context, outcomes, evidence builders, identifier lookup."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from verireview.contracts import (
    CodeLocation,
    Evidence,
    EvidenceSource,
    Requirement,
    ReviewCase,
    ReviewRequirement,
)
from verireview.rules.analysis import Scope, scope_of
from verireview.syntax import TargetResolution, parse, resolve_target

_BACKTICK_IDENT = re.compile(r"`\.?([A-Za-z_][\w.]*)(?:\([^`]*\))?`")
_WORD = re.compile(r"[A-Za-z_]\w*")
_CONSTANTS = frozenset({"None", "True", "False"})


class RuleStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    INCONCLUSIVE = "inconclusive"  # the rule cannot decide → feeds UNCERTAIN


@dataclass(frozen=True)
class RuleOutcome:
    status: RuleStatus
    summary: str
    evidence: list[Evidence] = field(default_factory=list)
    already_present: bool = False  # ADR-001: satisfied by code that predates the comment


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule may look at for one case (built once, shared by all requirements)."""

    case: ReviewCase
    requirement_set: ReviewRequirement
    resolution: TargetResolution
    before: Scope  # target symbol before (or the module)
    after: Scope  # target symbol after, plus where its code moved (or the module)
    before_file: Scope
    after_file: Scope

    @property
    def comment(self) -> str:
        return self.case.thread.root.body

    @property
    def file(self) -> str:
        return self.case.file_path

    @property
    def guarded_line(self) -> int | None:
        """Where the commented statement now is: the operation a guard must precede."""
        return self.resolution.anchor_after_line

    @classmethod
    def build(cls, case: ReviewCase, requirement_set: ReviewRequirement) -> "RuleContext | None":
        if case.before_code is None or case.after_code is None or case.anchor_line is None:
            return None
        resolution = resolve_target(case.before_code, case.after_code, case.anchor_line)
        if resolution.before is None:
            before = scope_of(case.before_code)
            after = scope_of(case.after_code)
        else:
            before = Scope((resolution.before.node,))
            after = Scope(
                tuple(s.node for s in (resolution.after, resolution.moved_to) if s is not None)
            )
        return cls(
            case=case,
            requirement_set=requirement_set,
            resolution=resolution,
            before=before,
            after=after,
            before_file=Scope((parse(case.before_code).root_node,)),
            after_file=Scope((parse(case.after_code).root_node,)),
        )


Rule = Callable[[Requirement, RuleContext], RuleOutcome]


# ---------------------------------------------------------------- identifiers in the request


def quoted_identifiers(text: str) -> list[str]:
    """Backticked identifiers, in order: "`username`", "`.json()`" → "username", "json"."""
    return [q for q in _BACKTICK_IDENT.findall(text) if q not in _CONSTANTS]


def requested_identifiers(requirement: Requirement, ctx: RuleContext) -> list[str]:
    """Code identifiers the requirement talks about, most specific first.

    Order: its target, backticked names in its text, then plain words (and word pairs joined by
    "_") that are identifiers in the code before the change. Only names present in the code.
    """
    known = ctx.before_file.identifiers | ctx.after_file.identifiers
    text = " ".join(t for t in (requirement.description, requirement.condition or "") if t)
    candidates: list[str] = []
    if requirement.target:
        candidates.append(requirement.target)
    candidates += quoted_identifiers(text)
    words = [w for w in _WORD.findall(re.sub(r"`[^`]*`", " ", text))]
    candidates += words + [f"{a}_{b}".lower() for a, b in zip(words, words[1:], strict=False)]
    seen: list[str] = []
    for name in candidates:
        root = name.split(".")[0]
        if root in known and root not in seen and root not in _CONSTANTS:
            seen.append(root)
    return seen


# ---------------------------------------------------------------- evidence builders


def located(
    requirement: Requirement,
    kind: str,
    passed: bool | None,
    detail: str,
    file: str,
    line: int,
    end: int | None = None,
    version: str = "after",
) -> Evidence:
    return Evidence(
        id="?",
        requirement_id=requirement.id,
        source=EvidenceSource.RULE,
        kind=kind,
        passed=passed,
        detail=detail,
        location=CodeLocation(file=file, line_start=line, line_end=end or line, version=version),
    )


def unlocated(
    requirement: Requirement, kind: str, passed: bool | None, detail: str, reason: str
) -> Evidence:
    return Evidence(
        id="?",
        requirement_id=requirement.id,
        source=EvidenceSource.RULE,
        kind=kind,
        passed=passed,
        detail=detail,
        no_location_reason=reason,
    )


def inconclusive(requirement: Requirement, why: str) -> RuleOutcome:
    return RuleOutcome(
        RuleStatus.INCONCLUSIVE,
        why,
        [unlocated(requirement, "rule.inconclusive", None, why, "nothing to point at")],
    )
