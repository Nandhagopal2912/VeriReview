"""Testing rule (plan §12): "Add a unit test for invalid username."

1. Was a test added or changed? (new/changed test functions in the window's test files)
2. Does it call the function under test? (named in the request, else the commented function)
3. Does it exercise the requested case? The case is read from the request ("empty", "None",
   "negative", "timeout", explicit numbers…) and checked against the test *body*: its literal
   inputs and identifiers. A test merely *named* `test_timeout_case` does not count.
ADR-001: an unchanged existing test already covering the case → satisfied, already present.
"""

import re
from collections.abc import Callable

from verireview.contracts import Requirement
from verireview.rules.analysis import TestFunction, changed_test_functions, find_test_functions
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
    located,
    quoted_identifiers,
    unlocated,
)

_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w%])")


def _has_string(pred: Callable[[str], bool]) -> Callable[[TestFunction], bool]:
    return lambda t: any(pred(s) for s in t.strings)


# Case word in the request → how a test body demonstrates it.
_CASES: dict[str, tuple[re.Pattern[str], Callable[[TestFunction], bool]]] = {
    "empty": (re.compile(r"\bempty\b", re.I), _has_string(lambda s: s == "")),
    "blank": (re.compile(r"\bblank\b", re.I), _has_string(lambda s: s.strip() == "")),
    "None": (re.compile(r"\b(none|null)\b", re.I), lambda t: t.uses_none),
    "negative": (re.compile(r"\bnegative\b", re.I), lambda t: any(n < 0 for n in t.numbers)),
    "zero": (re.compile(r"\b(zero|0-\w+|0 \w+)\b", re.I), lambda t: 0 in t.numbers),
    "timeout": (
        re.compile(r"\btime ?outs?\b", re.I),
        lambda t: any("timeout" in i.lower() for i in t.body_identifiers),
    ),
}


def testing_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    function = _function_under_test(requirement, ctx)
    if function is None:
        return inconclusive(requirement, "The function under test cannot be identified.")
    wanted = _requested_cases(requirement.description)
    values = [float(v) for v in _NUMBER.findall(_unquoted_numbers(requirement.description))]

    changed = changed_test_functions(ctx.case.test_files, ctx.case.test_files_before)
    existing = _unchanged_tests(ctx)

    if not changed:
        covering = [t for t in existing if t.calls(function) and _covers(t, wanted, values)]
        if covering:
            t = covering[0]
            return RuleOutcome(
                RuleStatus.SATISFIED,
                "An existing test already covers the case.",
                [
                    located(
                        requirement,
                        "already_present",
                        True,
                        f"Existing test `{t.qualified_name}` already covers it (ADR-001).",
                        t.path,
                        t.line,
                    )
                ],
                already_present=True,
            )
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            "No test was added or changed.",
            [
                unlocated(
                    requirement,
                    "testing.no_new_test",
                    False,
                    "No test function was added or changed.",
                    "absence has no location",
                )
            ],
        )

    calling = [t for t in changed if t.calls(function)]
    if not calling:
        other = sorted({c for t in changed for c in t.callees if "." not in c})
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"New tests do not call `{function}`.",
            [
                located(
                    requirement,
                    "testing.wrong_function",
                    False,
                    f"New test `{changed[0].qualified_name}` does not call `{function}`"
                    + (f" (it calls {', '.join(f'`{c}`' for c in other)})." if other else "."),
                    changed[0].path,
                    changed[0].line,
                )
            ],
        )

    matching = [t for t in calling if _covers(t, wanted, values)]
    if not matching:
        t = calling[0]
        case = ", ".join(wanted + [str(v) for v in values])
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"No new test exercises the {case} case.",
            [
                located(
                    requirement,
                    "testing.case_not_exercised",
                    False,
                    f"`{t.qualified_name}` calls `{function}` but never uses a {case} input.",
                    t.path,
                    t.line,
                )
            ],
        )

    t = matching[0]
    what = f" with a {', '.join(wanted)} input" if wanted else ""
    return RuleOutcome(
        RuleStatus.SATISFIED,
        f"`{t.qualified_name}` tests `{function}`{what}.",
        [
            located(
                requirement,
                "testing.case_exercised",
                True,
                f"New test `{t.qualified_name}` calls `{function}`{what}.",
                t.path,
                t.line,
            )
        ],
    )


def _function_under_test(requirement: Requirement, ctx: RuleContext) -> str | None:
    defined = ctx.before_file.defined_names() | ctx.after_file.defined_names()
    for name in [requirement.target or "", *quoted_identifiers(requirement.description)]:
        if name.split(".")[-1] in defined:
            return name.split(".")[-1]
    symbol = ctx.resolution.after or ctx.resolution.before
    return symbol.name if symbol is not None and symbol.kind != "class" else None


def _requested_cases(text: str) -> list[str]:
    return [name for name, (pattern, _) in _CASES.items() if pattern.search(text)]


def _unquoted_numbers(text: str) -> str:
    """Numbers stated in the request, excluding identifiers like `test_2` in backticks."""
    return re.sub(r"`[A-Za-z_][^`]*`", " ", text)


def _covers(test: TestFunction, wanted: list[str], values: list[float]) -> bool:
    if any(not _CASES[name][1](test) for name in wanted):
        return False
    return not values or any(v in test.numbers for v in values)


def _unchanged_tests(ctx: RuleContext) -> list[TestFunction]:
    tests: list[TestFunction] = []
    for path, code in ctx.case.test_files_before.items():
        tests += find_test_functions(path, code)
    return tests
