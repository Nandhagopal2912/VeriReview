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

Phase 10.3 (from the v2 cases, now dev data):
- polarity: the check must reject what the request rejects. `if limit >= 0: raise` does not
  validate "not negative". The condition is evaluated for sample values the request implies
  (`_polarity_ok`); a condition that cannot be evaluated is not second-guessed.
- a check behind an unrelated flag (`if DEBUG and source is target: raise`) is not the requested
  validation: dead when the flag is a module constant that is False, otherwise it cannot be told
  whether it runs (inconclusive).
- "are dates" / "is a list" ask for a type check.
"""

import ast
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
        r"\b(an? )?(int|integer|str|string|float|bool|number|type|isinstance)\b|"
        r"\b(?:is|are|be)\s+(?:both\s+)?(?:an?\s+)?(?:valid\s+)?"
        r"(dates?|datetimes?|strings?|integers?|ints?|numbers?|lists?|dicts?|tuples?|booleans?|"
        r"floats?|bytes)\b",
        re.I,
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
    flagged = [
        (g, flag)
        for g in on_target
        if (flag := _unrelated_flag(g, target)) is not None and _flag_runs(flag, ctx) is not True
    ]
    on_target = [g for g in on_target if all(g is not f for f, _ in flagged)]
    evidence = []
    missing: list[str] = []
    chosen: list[Guard] = []
    wrong_bounds: list[Guard] = []
    for kind in kinds:
        candidates = [g for g in on_target if g.rejects and _is_kind(g, kind)]
        if kind == "range":
            fitting = [
                g
                for g in candidates
                if _bounds_ok(g.condition.text, text) and _polarity_ok(g, text, target)
            ]
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
        behind_flag = _behind_flag(requirement, ctx, names, flagged)
        if behind_flag is not None:
            return RuleOutcome(
                behind_flag.status, behind_flag.summary, evidence + behind_flag.evidence
            )
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


_SAMPLE_NUM = r"(-?\d+(?:\.\d+)?)"
_BETWEEN = re.compile(rf"\bbetween\s+{_SAMPLE_NUM}\s+and\s+{_SAMPLE_NUM}", re.I)
_AT_LEAST = re.compile(rf"\b(?:at least|minimum(?: of)?|no less than)\s+{_SAMPLE_NUM}", re.I)
_AT_MOST = re.compile(rf"\b(?:at most|maximum(?: of)?|no more than)\s+{_SAMPLE_NUM}", re.I)
_NOT_NEGATIVE = re.compile(r"\b(?:not|non)[- ]?negative\b|\bnonnegative\b", re.I)


def _samples(request: str) -> tuple[list[float], list[float]]:
    """Values the request says must pass, and values it says must be rejected."""
    plain = re.sub(r"`[^`]*`", " ", request)
    if m := _BETWEEN.search(plain):
        low, high = sorted((float(m.group(1)), float(m.group(2))))
        return [(low + high) / 2], [low - 1, high + 1]  # the ends may or may not be included
    if m := _AT_LEAST.search(plain):
        return [float(m.group(1))], [float(m.group(1)) - 1]
    if m := _AT_MOST.search(plain):
        return [float(m.group(1))], [float(m.group(1)) + 1]
    if _NOT_NEGATIVE.search(plain):
        return [0.0, 1.0], [-1.0]
    if re.search(r"\bpositive\b", plain, re.I):
        return [1.0], [-1.0]
    return [], []


def _polarity_ok(guard: Guard, request: str, target: set[str]) -> bool:
    """The guard rejects what the request rejects, and lets through what it allows.

    `if limit >= 0: raise` for "not negative" rejects 0 and 1 and lets -1 through: the wrong way
    round. Only a condition on one requested variable that can be evaluated is judged; anything
    else (calls, other variables) passes unjudged.
    """
    names = guard.condition.identifiers & target
    accept, reject = _samples(request)
    if len(names) != 1 or not (accept or reject):
        return True
    name = next(iter(names))
    for value, must_reject in [(v, False) for v in accept] + [(v, True) for v in reject]:
        outcome = _evaluate(guard.condition.text, name, value)
        if outcome is None:
            continue
        rejected = (not outcome) if guard.kind == "assert" else outcome
        if rejected != must_reject:
            return False
    return True


def _compare(op: ast.cmpop, left: float, right: float) -> bool | None:
    match op:
        case ast.Lt():
            return left < right
        case ast.LtE():
            return left <= right
        case ast.Gt():
            return left > right
        case ast.GtE():
            return left >= right
        case ast.Eq():
            return left == right
        case ast.NotEq():
            return left != right
        case _:
            return None


def _evaluate(condition: str, name: str, value: float) -> bool | None:
    """Truth of ``condition`` when ``name`` (or ``len(name)``) is ``value``; None = cannot tell.

    Three-valued: a part that cannot be evaluated (another variable, a call) is unknown, and
    `and` / `or` are decided only when the known parts decide them. Nothing is executed.
    """
    try:
        tree = ast.parse(condition.strip(), mode="eval")
    except SyntaxError:
        return None

    def number(node: ast.expr) -> float | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return None if isinstance(node.value, bool) else float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = number(node.operand)
            return None if inner is None else -inner
        if isinstance(node, ast.Name) and node.id == name:
            return value
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "len"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == name
        ):
            return value
        return None

    def truth(node: ast.expr) -> bool | None:
        if isinstance(node, ast.BoolOp):
            parts = [truth(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return False if False in parts else (None if None in parts else True)
            return True if True in parts else (None if None in parts else False)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            inner = truth(node.operand)
            return None if inner is None else not inner
        if isinstance(node, ast.Compare):
            left = number(node.left)
            for op, right_node in zip(node.ops, node.comparators, strict=True):
                right = number(right_node)
                if left is None or right is None:
                    return None
                outcome = _compare(op, left, right)
                if outcome is None:
                    return None
                if not outcome:
                    return False
                left = right
            return True
        return None

    return truth(tree.body)


_FLAG_VALUE = r"^{name}\s*(?::\s*bool\s*)?=\s*(True|False)\s*(?:#.*)?$"


def _unrelated_flag(guard: Guard, target: set[str]) -> str | None:
    """A bare name the whole check is conditional on: `if DEBUG and x < 0` gives "DEBUG".

    Only a top-level `and` with a conjunct that is a plain name or attribute (possibly negated)
    and not one of the requested variables. `if x is not None and x < 0` has no such conjunct.
    """
    if guard.kind == "assert":
        return None
    try:
        tree = ast.parse(guard.condition.text.strip(), mode="eval").body
    except SyntaxError:
        return None
    if not (isinstance(tree, ast.BoolOp) and isinstance(tree.op, ast.And)):
        return None
    for part in tree.values:
        negated = isinstance(part, ast.UnaryOp) and isinstance(part.op, ast.Not)
        node = part.operand if isinstance(part, ast.UnaryOp) and negated else part
        if isinstance(node, ast.Name | ast.Attribute):
            text = ast.unparse(node)
            if text not in target and text.split(".")[0] not in target:
                return ("not " if negated else "") + text
    return None


def _flag_runs(flag: str, ctx: RuleContext) -> bool | None:
    """Whether a check behind ``flag`` runs: known only for a module constant True/False."""
    name = flag.removeprefix("not ")
    constant = re.search(_FLAG_VALUE.format(name=re.escape(name)), ctx.case.after_code or "", re.M)
    if constant is None:
        return None
    return (constant.group(1) == "True") != flag.startswith("not ")


def _behind_flag(
    requirement: Requirement, ctx: RuleContext, names: list[str], flagged: list[tuple[Guard, str]]
) -> RuleOutcome | None:
    """The only check on the variable is conditional on an unrelated flag."""
    relevant = [(g, flag) for g, flag in flagged if g.rejects]
    if not relevant:
        return None
    guard, flag = relevant[0]
    name = flag.removeprefix("not ")
    if _flag_runs(flag, ctx) is False:
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"The check on `{names[0]}` never runs: it needs `{flag}`.",
            [
                located(
                    requirement,
                    "validation.check_disabled_by_flag",
                    False,
                    f"`{guard.condition.text}` only runs when `{flag}` holds, and this file "
                    f"sets `{name}` to a constant that rules that out.",
                    ctx.file,
                    guard.line,
                    guard.end_line,
                )
            ],
        )
    return RuleOutcome(
        RuleStatus.INCONCLUSIVE,
        f"The check on `{names[0]}` only runs when `{flag}` holds.",
        [
            located(
                requirement,
                "validation.check_behind_flag",
                None,
                f"`{guard.condition.text}` depends on `{flag}`, which the request does not "
                "mention; whether the check runs cannot be told from this file.",
                ctx.file,
                guard.line,
                guard.end_line,
            )
        ],
    )


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
