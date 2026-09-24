"""Validation rule (plan §12): "Add a null check before saving."

For the variable(s) the request names, the code after the change must contain a guard that
1. tests that variable (a check on another variable does not count),
2. is of the requested kind (None / empty / range / type; any check for a generic "validate"),
3. rejects: its branch raises or returns (a check that only logs changes nothing), and
4. runs before the guarded operation (the commented statement) when that can be located.
ADR-001: a matching guard that already existed before the comment → satisfied, already present.

Phase 10.1: a range check must use the requested bound ("at least 1" is not `x < 0`, "positive"
is not `x < 0`); a check in `__post_init__` or another method is not "too late" for a field it
guards; a pydantic model built from the value (`Model(amount=amount)` with
`amount: float = Field(gt=0)`, a constrained type or a field validator) is a delegated check.
"""

import re

from verireview.contracts import Evidence, Requirement
from verireview.rules.analysis import (
    Guard,
    Scope,
    call_arguments,
    function_parameters,
    model_constraint,
)
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
_KIND_LABEL = {
    "type": "Type check",
    "none": "None check",
    "empty": "Emptiness check",
    "range": "Range check",
    "any": "Check",
}
_VALIDATOR_NAME = re.compile(r"^_?(validate|check|ensure|verify|assert|require)", re.I)


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
    wrong_bounds: list[Guard] = []
    for kind in kinds:
        candidates = [g for g in on_target if g.rejects and _is_kind(g, kind)]
        if kind == "range":
            fitting = [g for g in candidates if _bounds_ok(g.condition.text, text)]
            wrong_bounds += [g for g in candidates if g not in fitting]
            candidates = fitting
        guard = candidates[0] if candidates else None
        if guard is None:
            missing.append(kind)
            continue
        chosen.append(guard)
        evidence.append(
            located(
                requirement,
                f"validation.{kind}_check",
                True,
                f"{_KIND_LABEL[kind]} `{guard.condition.text}` on `{_names(guard, target)}` "
                f"{_rejection(guard)} (line {guard.line}).",
                ctx.file,
                guard.line,
                guard.end_line,
            )
        )

    if missing:
        delegated = _delegated(requirement, ctx, names, missing)
        if delegated is not None:
            return RuleOutcome(
                delegated.status,
                delegated.summary,
                evidence + delegated.evidence,
                already_present=delegated.already_present,
            )
        evidence += [
            located(
                requirement,
                "validation.wrong_bound",
                False,
                f"`{g.condition.text}` checks `{names[0]}` against the wrong bound for "
                f'"{requirement.description}".',
                ctx.file,
                g.line,
            )
            for g in wrong_bounds
        ]
        evidence += _explain_missing(requirement, ctx, names, missing, on_target)
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"No rejecting {'/'.join(missing)} check on `{names[0]}`.",
            evidence,
        )

    operation = ctx.guarded_line
    late = [
        g
        for g in chosen
        if operation is not None
        and g.line > operation
        and _enclosing_function(ctx, g.line) == _enclosing_function(ctx, operation)
    ]
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


def _delegated(
    requirement: Requirement, ctx: RuleContext, names: list[str], kinds: list[str]
) -> RuleOutcome | None:
    """Validation done by a function called with the variable before the operation.

    A helper defined in the same file is analysed one level deep (argument → parameter →
    rejecting guard of the requested kind), which can satisfy the rule. A helper that is not in
    the file but is named like a validator cannot be inspected, so the result is inconclusive
    (→ human review) rather than a verdict either way.
    """
    operation = ctx.guarded_line
    for call in sorted(ctx.after.facts.calls, key=lambda c: c.line):
        if operation is not None and call.line >= operation:
            continue
        args = call_arguments(call.text, call.callee)
        if not any(value in names for _, value in args):
            continue
        callee = call.callee.split(".")[-1]
        helper = ctx.after_file.function(callee)
        model = ctx.after_file.class_definition(callee)
        if model is not None:
            fields = {key for key, value in args if key and value in names}
            constraint = next(
                (c for f in fields if (c := model_constraint(model, f)) is not None), None
            )
            if constraint is not None:
                return RuleOutcome(
                    RuleStatus.SATISFIED,
                    f"`{callee}` validates `{names[0]}` when it is built.",
                    [
                        located(
                            requirement,
                            "validation.checked_by_model",
                            True,
                            f"`{call.text}` (line {call.line}) builds `{callee}`, whose field "
                            f"is constrained by `{constraint}`.",
                            ctx.file,
                            call.line,
                        )
                    ],
                )
        if helper is not None:
            params = function_parameters(helper)
            checked = {
                key or (params[i] if i < len(params) else "")
                for i, (key, value) in enumerate(args)
                if value in names
            }
            guards = [
                g
                for g in Scope((helper,)).guards()
                if g.rejects and g.condition.identifiers & checked
            ]
            per_kind = [next((g for g in guards if _is_kind(g, kind)), None) for kind in kinds]
            found = [g for g in per_kind if g is not None]
            if found and len(found) == len(kinds):
                g = found[0]
                return RuleOutcome(
                    RuleStatus.SATISFIED,
                    f"`{callee}` checks `{names[0]}` before use.",
                    [
                        located(
                            requirement,
                            "validation.checked_in_helper",
                            True,
                            f"`{call.text}` (line {call.line}) runs `{g.condition.text}` in "
                            f"`{callee}`, which {_rejection(g)} (line {g.line}).",
                            ctx.file,
                            g.line,
                            g.end_line,
                        )
                    ],
                )
        elif _VALIDATOR_NAME.match(callee):
            return RuleOutcome(
                RuleStatus.INCONCLUSIVE,
                f"Validation is delegated to `{callee}`, which is not in this file.",
                [
                    located(
                        requirement,
                        "validation.delegated",
                        None,
                        f"`{call.text}` may validate `{names[0]}`, but `{callee}` is defined "
                        "elsewhere and was not analysed.",
                        ctx.file,
                        call.line,
                    )
                ],
            )
    return None


_NUMBER = re.compile(r"(?<![\w.`])-?\d+(?:\.\d+)?(?![\w`])")
_NUM = r"-?\d+(?:\.\d+)?"
# "x < 5" and "5 > x": each literal with the operator that compares it to the variable.
_VAR_OP_NUM = re.compile(rf"(<=|>=|<|>|==|!=)\s*({_NUM})(?![\w.])")
_NUM_OP_VAR = re.compile(rf"(?<![\w.])({_NUM})\s*(<=|>=|<|>|==|!=)")
_FLIP = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}


def _comparisons(condition: str) -> set[tuple[str, float]]:
    """(operator, literal) with the variable on the left: `1 <= x` → (">=", 1.0)."""
    pairs = {(op, float(n)) for op, n in _VAR_OP_NUM.findall(condition)}
    pairs |= {(_FLIP[op], float(n)) for n, op in _NUM_OP_VAR.findall(condition)}
    return pairs


def _bounds_ok(condition: str, request: str) -> bool:
    """The rejecting condition uses the requested bound (or its integer equivalent).

    "at least 1": `x < 1` or `x <= 0`, not `x < 0`. "positive": rejects 0 too (`x <= 0` /
    `x < 1`). "between 1 and 65535": both numbers. Requests without a bound are not checked.
    """
    pairs = _comparisons(condition)
    plain = re.sub(r"`[^`]*`", " ", request)
    wanted = [float(v) for v in _NUMBER.findall(plain)]
    if wanted:
        return all(_uses(n, pairs) for n in wanted)
    if re.search(r"\bpositive\b", plain, re.I):
        return bool(pairs & {("<=", 0.0), (">", 0.0), ("<", 1.0), (">=", 1.0)})
    return True


def _uses(bound: float, pairs: set[tuple[str, float]]) -> bool:
    """`bound` itself, or the integer next to it with the operator that means the same."""
    if any(value == bound for _, value in pairs):
        return True
    below = {("<=", bound - 1), (">", bound - 1)}
    above = {(">=", bound + 1), ("<", bound + 1)}
    return bool(pairs & (below | above))


def _enclosing_function(ctx: RuleContext, line: int) -> int | None:
    """Start line of the innermost function around ``line`` (None at class/module level)."""
    spans = ctx.after_file.function_spans()
    inside = [(start, end) for start, end in spans if start <= line <= end]
    return max(inside)[0] if inside else None


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
