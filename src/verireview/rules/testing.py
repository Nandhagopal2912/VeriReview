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
from verireview.requirements import lexicon as lx
from verireview.rules.analysis import (
    TestFunction,
    changed_test_functions,
    find_test_functions,
    route_paths,
)
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
    "empty": (
        re.compile(r"\bempty\b", re.I),
        lambda t: "" in t.strings or t.empty_collection,  # "" or [] / {} / ()
    ),
    "blank": (re.compile(r"\bblank\b", re.I), _has_string(lambda s: s.strip() == "")),
    "None": (re.compile(r"\b(none|null)\b", re.I), lambda t: t.uses_none),
    "negative": (re.compile(r"\bnegative\b", re.I), lambda t: any(n < 0 for n in t.numbers)),
    "zero": (re.compile(r"\b(zero|0-\w+|0 \w+)\b", re.I), lambda t: 0 in t.numbers),
    "timeout": (
        re.compile(r"\btime ?outs?\b", re.I),
        lambda t: any("timeout" in i.lower() for i in t.body_identifiers),
    ),
    "single": (
        re.compile(r"\bsingle\b|\bone[- ](?:item|element)\b", re.I),
        lambda t: t.singleton_collection,
    ),
}
_RAISE_WORD = re.compile(r"\b(raises?|raised|raising|throws?|thrown)\b", re.I)
_CLIENT_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "open"})
_DEF = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)", re.M)
# pytest / plugin fixtures whose behaviour is known (not scenario helpers).
_BUILTIN_FIXTURES = frozenset(
    {
        "request",
        "tmp_path",
        "tmpdir",
        "tmp_path_factory",
        "monkeypatch",
        "capsys",
        "capfd",
        "caplog",
        "recwarn",
        "mocker",
        "pytester",
        "testdir",
        "client",
        "app",
        "rf",
        "settings",
        "db",
        "event_loop",
    }
)
_SCENARIO_STOPWORDS = frozenset(
    {
        "add",
        "adds",
        "test",
        "tests",
        "testing",
        "for",
        "the",
        "and",
        "that",
        "this",
        "case",
        "cases",
        "with",
        "when",
        "check",
        "checks",
        "should",
        "one",
        "also",
        "another",
        "please",
        "new",
        "input",
        "value",
    }
)


def testing_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    function = _function_under_test(requirement, ctx)
    if function is None:
        return inconclusive(requirement, "The function under test cannot be identified.")
    wanted = _requested_cases(requirement.description)
    values = [float(v) for v in _NUMBER.findall(_unquoted_numbers(requirement.description))]
    raised = _requested_exceptions(requirement.description)
    routes = _route_prefixes(function, ctx)

    changed = changed_test_functions(ctx.case.test_files, ctx.case.test_files_before)
    runnable = [t for t in changed if not t.skipped]

    if not runnable:
        if changed:
            t = changed[0]
            return _fail(
                requirement,
                "testing.test_skipped",
                f"`{t.qualified_name}` is skipped (skip/xfail), so it demonstrates nothing.",
                t,
            )
        return _existing_or_missing(requirement, ctx, function, routes, wanted, values, raised)

    calling = [t for t in runnable if _exercises(t, function, routes)]
    if not calling:
        opaque = next(((t, f) for t in runnable for f in _opaque_fixtures(t, ctx)), None)
        if opaque is not None:
            t, fixture = opaque
            return RuleOutcome(
                RuleStatus.INCONCLUSIVE,
                f"`{t.qualified_name}` goes through fixture `{fixture}`, defined elsewhere.",
                [
                    located(
                        requirement,
                        "testing.opaque_fixture",
                        None,
                        f"`{t.qualified_name}` does not call `{function}` itself; it uses "
                        f"fixture `{fixture}`, which is not in the changed files, so what it "
                        "runs cannot be checked.",
                        t.path,
                        t.line,
                    )
                ],
            )
        other = sorted({c for t in runnable for c in t.callees if "." not in c})
        return _fail(
            requirement,
            "testing.wrong_function",
            f"New test `{runnable[0].qualified_name}` does not call `{function}`"
            + (f" (it calls {', '.join(f'`{c}`' for c in other)})." if other else "."),
            runnable[0],
            summary=f"New tests do not call `{function}`.",
        )

    asserting = [t for t in calling if t.has_expectation]
    if not asserting:
        t = calling[0]
        return _fail(
            requirement,
            "testing.no_expectation",
            f"`{t.qualified_name}` calls `{function}` but asserts nothing (no assert, "
            "pytest.raises or assert* call).",
            t,
        )

    matching = [t for t in asserting if _covers(t, wanted, values, raised)]
    if not matching:
        t = asserting[0]
        case = ", ".join(wanted + [str(v) for v in values] + raised)
        if wanted or values:
            detail = f"`{t.qualified_name}` calls `{function}` but never uses a {case} input."
        else:
            expected = " / ".join(f"`{e}`" for e in raised)
            detail = (
                f"`{t.qualified_name}` calls `{function}` but does not expect {expected} "
                "(pytest.raises / assertRaises)."
            )
        return _fail(
            requirement,
            "testing.case_not_exercised",
            detail,
            t,
            summary=f"No new test exercises the {case} case.",
        )

    # A demonstrated case (None, zero, a value, an exception) already pins the test to this
    # requirement; only a scenario in plain words needs a test that mentions it.
    distinctive = set() if wanted or values or raised else _distinctive_words(requirement, ctx)
    if distinctive:
        specific = [t for t in matching if _mentions(t, distinctive)]
        if not specific:
            t = matching[0]
            words = ", ".join(sorted(distinctive))
            return _fail(
                requirement,
                "testing.scenario_not_targeted",
                f"`{t.qualified_name}` tests another requested case; no new test targets "
                f"this one ({words}).",
                t,
                summary=f"No new test targets this case ({words}).",
            )
        matching = specific

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


def _existing_or_missing(
    requirement: Requirement,
    ctx: RuleContext,
    function: str,
    routes: list[str],
    wanted: list[str],
    values: list[float],
    raised: list[str],
) -> RuleOutcome:
    """No new runnable test. ADR-001: an unchanged test that demonstrably covers the case.

    Only a request with a checkable case (a case word, a value or an expected exception) can be
    matched to an existing test; "a test for restocking" cannot, so it stays not satisfied.
    """
    if wanted or values or raised:
        for t in _unchanged_tests(ctx):
            if (
                not t.skipped
                and t.has_expectation
                and _exercises(t, function, routes)
                and _covers(t, wanted, values, raised)
            ):
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
                "No test function was added or changed (a renamed or skipped test does not count).",
                "absence has no location",
            )
        ],
    )


def _fail(
    requirement: Requirement, kind: str, detail: str, test: TestFunction, summary: str = ""
) -> RuleOutcome:
    return RuleOutcome(
        RuleStatus.NOT_SATISFIED,
        summary or detail,
        [located(requirement, kind, False, detail, test.path, test.line)],
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


def _covers(test: TestFunction, wanted: list[str], values: list[float], raised: list[str]) -> bool:
    if any(not _CASES[name][1](test) for name in wanted):
        return False
    if raised and not any(e in expected for e in raised for expected in test.expected_exceptions):
        return False
    return not values or any(v in test.numbers for v in values)


def _requested_exceptions(text: str) -> list[str]:
    """ "a test that … raises ValueError" → the test must expect ValueError."""
    if not _RAISE_WORD.search(text):
        return []
    return list(dict.fromkeys(lx.EXCEPTION_NAME.findall(text)))


def _route_prefixes(function: str, ctx: RuleContext) -> list[str]:
    """Static URL prefixes of a web handler: @app.get("/orders/<int:id>") → "/orders/"."""
    prefixes: list[str] = []
    for scope in (ctx.after_file, ctx.before_file):
        definition = scope.function(function)
        if definition is not None:
            prefixes += [p for p in route_paths(definition) if len(p) > 1]
    return list(dict.fromkeys(prefixes))


def _exercises(test: TestFunction, function: str, routes: list[str]) -> bool:
    """Calls the function, or requests its URL through a test client."""
    if test.calls(function):
        return True
    via_client = any(c.split(".")[-1] in _CLIENT_METHODS for c in test.callees)
    return via_client and any(s.startswith(p) for s in test.strings for p in routes)


def _opaque_fixtures(test: TestFunction, ctx: RuleContext) -> list[str]:
    """Fixtures the test uses whose definition is not in the changed files."""
    defined: set[str] = set()
    for code in ctx.case.test_files.values():
        defined |= set(_DEF.findall(code))
    used = set(test.callees) | test.body_identifiers
    return [
        p for p in test.parameters if p not in _BUILTIN_FIXTURES and p not in defined and p in used
    ]


def _distinctive_words(requirement: Requirement, ctx: RuleContext) -> set[str]:
    """Scenario words of this testing requirement that its sibling testing requirements lack.

    "Add tests for removing more than in stock and for an unknown SKU" gives two requirements;
    one test cannot be claimed by both, so each needs a test that mentions its own scenario.
    """
    siblings = [
        r
        for r in ctx.requirement_set.requirements
        if r.id != requirement.id and r.category == requirement.category
    ]
    if not siblings:
        return set()
    others = set().union(*(_scenario_words(r.description) for r in siblings))
    return _scenario_words(requirement.description) - others


def _scenario_words(text: str) -> set[str]:
    words = re.findall(r"[a-z]{3,}", _unquoted_numbers(text).lower())
    return {w[:5] for w in words if w not in _SCENARIO_STOPWORDS}


def _mentions(test: TestFunction, stems: set[str]) -> bool:
    parts = re.split(r"[_.]", test.qualified_name.lower())
    parts += [p for i in test.body_identifiers for p in i.lower().split("_")]
    parts += [w for s in test.strings for w in re.findall(r"[a-z]{3,}", s.lower())]
    return bool({p[:5] for p in parts if len(p) >= 3} & stems)


def _unchanged_tests(ctx: RuleContext) -> list[TestFunction]:
    tests: list[TestFunction] = []
    for path, code in ctx.case.test_files_before.items():
        tests += find_test_functions(path, code)
    return tests
