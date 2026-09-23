"""Validation rule (plan §12): "Add a null check before saving."

For the variable(s) the request names, the code after the change must contain a guard that
1. tests that variable (a check on another variable does not count),
2. is of the requested kind (None / empty / range / type; any check for a generic "validate"),
3. rejects: its branch raises or returns (a check that only logs changes nothing), and
4. runs before the guarded operation (the commented statement) when that can be located.
ADR-001: a matching guard that already existed before the comment → satisfied, already present.
"""

import re

from verireview.contracts import Evidence, Requirement
from verireview.rules.analysis import Guard
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
    located,
    requested_identifiers,
    unlocated,
)

_KINDS = {
    "type": re.compile(
        r"\b(an? )?(int|integer|str|string|float|bool|number|type|isinstance)\b", re.I
    ),
    "none": re.compile(r"\b(none|null|nil)\b", re.I),
    "empty": re.compile(r"\b(empty|blank|non-empty)\b", re.I),
    "range": re.compile(
        r"\b(between|positive|negative|range|at (most|least)|max(imum)?|min(imum)?|greater|"
        r"less|longer|shorter)\b|[<>]",
        re.I,
    ),
}
_COMPARISON = re.compile(r"(<=|>=|<|>|\bin range\b)")


def validation_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    names = requested_identifiers(requirement, ctx)
    if not names:
        return inconclusive(requirement, "The request does not name a variable to validate.")
    text = f"{requirement.description} {requirement.condition or ''}"
    kinds = [k for k, pattern in _KINDS.items() if pattern.search(text)] or ["any"]
    target = set(names)

    on_target = [g for g in ctx.after.guards() if g.condition.identifiers & target]
    evidence = []
    missing: list[str] = []
    chosen: list[Guard] = []
    for kind in kinds:
        guard = next((g for g in on_target if g.rejects and _is_kind(g, kind)), None)
        if guard is None:
            missing.append(kind)
            continue
        chosen.append(guard)
        evidence.append(
            located(
                requirement,
                f"validation.{kind}_check",
                True,
                f"`{guard.condition.text}` checks `{_names(guard, target)}` and "
                f"{_rejection(guard)} (line {guard.line}).",
                ctx.file,
                guard.line,
                guard.end_line,
            )
        )

    if missing:
        evidence += _explain_missing(requirement, ctx, names, missing, on_target)
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"No rejecting {'/'.join(missing)} check on `{names[0]}`.",
            evidence,
        )

    operation = ctx.guarded_line
    late = [g for g in chosen if operation is not None and g.line > operation]
    if late:
        evidence.append(
            located(
                requirement,
                "validation.check_after_operation",
                False,
                f"The check on line {late[0].line} runs after the commented operation on "
                f"line {operation}.",
                ctx.file,
                late[0].line,
            )
        )
        return RuleOutcome(RuleStatus.NOT_SATISFIED, "The check runs too late.", evidence)

    before_conditions = {g.condition.text for g in ctx.before.guards() if g.rejects}
    already = all(g.condition.text in before_conditions for g in chosen)
    if already:
        evidence.append(
            unlocated(
                requirement,
                "already_present",
                True,
                "The requested check already existed before the comment (ADR-001).",
                "state predates the comment",
            )
        )
    return RuleOutcome(
        RuleStatus.SATISFIED,
        f"`{names[0]}` is checked before use.",
        evidence,
        already_present=already,
    )


def _is_kind(guard: Guard, kind: str) -> bool:
    condition = guard.condition
    match kind:
        case "none":
            return condition.checks_none
        case "empty":
            return condition.checks_empty
        case "type":
            return "isinstance(" in condition.text or "type(" in condition.text
        case "range":
            return _COMPARISON.search(condition.text) is not None
        case _:
            return True


def _names(guard: Guard, target: set[str]) -> str:
    return ", ".join(sorted(guard.condition.identifiers & target))


def _rejection(guard: Guard) -> str:
    if guard.kind == "assert":
        return "asserts"
    if guard.raises:
        return f"raises `{guard.raises[0].exception or 're-raise'}`"
    return f"returns `{guard.returns[0].value}`"


def _explain_missing(
    requirement: Requirement,
    ctx: RuleContext,
    names: list[str],
    missing: list[str],
    on_target: list[Guard],
) -> list[Evidence]:
    """Why it failed: a non-rejecting check, a check of another kind, or another variable."""
    items = []
    for guard in on_target:
        if not guard.rejects:
            items.append(
                located(
                    requirement,
                    "validation.check_does_not_reject",
                    False,
                    f"`{guard.condition.text}` exists but its branch neither raises nor returns.",
                    ctx.file,
                    guard.line,
                )
            )
    before_texts = {g.condition.text for g in ctx.before.guards()}
    new_elsewhere = [
        g for g in ctx.after.guards() if g.condition.text not in before_texts and g not in on_target
    ]
    for guard in new_elsewhere:
        other = ", ".join(sorted(guard.condition.identifiers)) or "other values"
        items.append(
            located(
                requirement,
                "validation.check_on_other_variable",
                False,
                f"A new check `{guard.condition.text}` tests {other}, not `{names[0]}`.",
                ctx.file,
                guard.line,
            )
        )
    if not items:
        items.append(
            unlocated(
                requirement,
                "validation.no_check",
                False,
                f"No {'/'.join(missing)} check on `{names[0]}` was found.",
                "absence has no location",
            )
        )
    return items
