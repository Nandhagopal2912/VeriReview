"""Structural queries the rules are built on (all over Tree-sitter nodes, never raw text).

- ``guards``: if / elif / assert conditions, with what their branch does (raise? return?)
- ``handlers``: except clauses, with what they protect and what their body does
- ``responses``: status codes produced by returns / aborts, with the branch conditions above them
- ``test_functions``: test functions, with the calls and literal inputs they use
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Literal

from tree_sitter import Node

from verireview.syntax.facts import (
    Call,
    CodeFacts,
    Condition,
    Handler,
    Raise,
    Return,
    condition_fact,
    descendants,
    extract_facts,
    handler_fact,
    normalized_text,
)
from verireview.syntax.parser import end_line, node_text, parse, start_line
from verireview.syntax.structure import structural_tokens
from verireview.syntax.symbols import index_symbols

HTTP_STATUS = frozenset(
    {
        200,
        201,
        202,
        204,
        301,
        302,
        304,
        400,
        401,
        403,
        404,
        405,
        409,
        410,
        415,
        422,
        429,
        500,
        502,
        503,
        504,
    }
)
# Calls whose integer argument is a response status: abort(404), HTTPException(status_code=404)…
_STATUS_CALLEES = ("abort", "HTTPException", "Response", "JSONResponse", "make_response")


@dataclass(frozen=True)
class BranchCondition:
    condition: Condition
    negated: bool  # True when inside the else branch of this condition


@dataclass(frozen=True)
class Guard:
    condition: Condition
    line: int
    end_line: int
    kind: Literal["if", "elif", "assert"]
    raises: tuple[Raise, ...]
    returns: tuple[Return, ...]
    calls: tuple[Call, ...] = ()  # calls in the guarded branch (e.g. a warning log)

    @property
    def rejects(self) -> bool:
        """The guarded branch stops normal execution (assert, raise or return)."""
        return self.kind == "assert" or bool(self.raises) or bool(self.returns)


@dataclass(frozen=True)
class HandlerInfo:
    handler: Handler
    end_line: int
    calls: tuple[Call, ...]  # calls in the except body
    raises: tuple[Raise, ...]
    returns: tuple[Return, ...]
    protected_calls: tuple[Call, ...]  # calls in the matching try body

    @property
    def line(self) -> int:
        return self.handler.line


@dataclass(frozen=True)
class StatusSite:
    code: int
    line: int
    text: str
    branch: tuple[BranchCondition, ...]  # innermost first


@dataclass(frozen=True)
class Scope:
    """A region of code (a target function, several functions, or a whole module)."""

    nodes: tuple[Node, ...]
    facts: CodeFacts = field(init=False, compare=False)

    def __post_init__(self) -> None:
        merged = CodeFacts()
        for node in self.nodes:
            merged = merged.merged(extract_facts(node))
        object.__setattr__(self, "facts", merged)

    @property
    def identifiers(self) -> frozenset[str]:
        return self.facts.identifiers

    def identifier_lines(self, name: str) -> list[int]:
        """Lines where ``name`` is used as an identifier (comments and strings excluded)."""
        return sorted(
            {start_line(n) for n in self._walk() if n.type == "identifier" and node_text(n) == name}
        )

    def guards(self) -> list[Guard]:
        found: list[Guard] = []
        for node in self._walk():
            if node.type in ("if_statement", "elif_clause"):
                condition = node.child_by_field_name("condition")
                body = node.child_by_field_name("consequence")
                if condition is None or body is None:
                    continue
                kind: Literal["if", "elif"] = "elif" if node.type == "elif_clause" else "if"
                facts = extract_facts(body)
                found.append(
                    Guard(
                        condition_fact(condition, kind),
                        start_line(node),
                        end_line(body),
                        kind,
                        facts.raises,
                        facts.returns,
                        facts.calls,
                    )
                )
            elif node.type == "assert_statement" and node.named_children:
                cond = condition_fact(node.named_children[0], "assert")
                found.append(Guard(cond, start_line(node), end_line(node), "assert", (), ()))
        return sorted(found, key=lambda g: g.line)

    def with_contexts(self) -> list[tuple[str, str, int]]:
        """(callee, text, line) of each `with` item that is a call: `with open(p) as f` → open."""
        found = []
        for node in self._walk():
            if node.type != "with_item":
                continue
            value = node.child_by_field_name("value") or (
                node.named_children[0] if node.named_children else None
            )
            if value is not None and value.type == "as_pattern" and value.named_children:
                value = value.named_children[0]
            if value is not None and value.type == "call":
                found.append((_callee_name(value), normalized_text(value), start_line(node)))
        return found

    def finally_calls(self) -> list[Call]:
        """Calls inside `finally:` blocks (cleanup that runs even when something fails)."""
        calls: list[Call] = []
        for node in self._walk():
            if node.type == "finally_clause":
                calls += extract_facts(node).calls
        return calls

    def handlers(self) -> list[HandlerInfo]:
        found: list[HandlerInfo] = self._suppressors()
        for node in self._walk():
            if node.type != "try_statement":
                continue
            body = node.child_by_field_name("body")
            protected = extract_facts(body).calls if body is not None else ()
            for clause in (c for c in node.named_children if c.type == "except_clause"):
                block = next((c for c in clause.named_children if c.type == "block"), None)
                facts = extract_facts(block) if block is not None else CodeFacts()
                found.append(
                    HandlerInfo(
                        handler_fact(clause),
                        end_line(clause),
                        facts.calls,
                        facts.raises,
                        facts.returns,
                        protected,
                    )
                )
        return found

    def _suppressors(self) -> list[HandlerInfo]:
        """`with contextlib.suppress(E):` is a handler for E whose body does nothing."""
        found = []
        for node in self._walk():
            if node.type != "with_statement":
                continue
            body = node.child_by_field_name("body")
            for callee, text, line in Scope((node,)).with_contexts():
                if callee.split(".")[-1] != "suppress":
                    continue
                exceptions = tuple(a for _, a in call_arguments(text, callee))
                fact = Handler("handler", f"with {text}", line, exceptions, True, False)
                protected = extract_facts(body).calls if body is not None else ()
                found.append(HandlerInfo(fact, end_line(node), (), (), (), protected))
                break
        return found

    def responses(self, exception_codes: dict[str, int] | None = None) -> list[StatusSite]:
        """HTTP status codes produced by returns, abort-like calls or raised HTTP exceptions.

        Codes may be literals (`404`), names (`HTTPStatus.NOT_FOUND`,
        `status.HTTP_404_NOT_FOUND`, `HttpResponseNotFound`), or exceptions mapped to a status
        (`raise Http404`, or an exception an `@app.errorhandler` turns into one). Code after an
        unconditional return/raise in the same block never runs and is skipped.
        """
        mapped = {**_EXCEPTION_STATUS, **(exception_codes or {})}
        sites: list[StatusSite] = []
        for node in self._walk():
            status_call = node.type == "call" and _callee_name(node).endswith(_STATUS_CALLEES)
            if node.type == "raise_statement":
                codes = [mapped[n] for n in [_raised_name(node)] if n in mapped]
            elif node.type == "return_statement" or status_call:
                codes = _status_literals(node) + _status_names(node)
            else:
                continue
            if not codes or _unreachable(node):
                continue
            for code in dict.fromkeys(codes):
                sites.append(
                    StatusSite(code, start_line(node), normalized_text(node), _branch(node))
                )
        return sites

    def defined_names(self) -> frozenset[str]:
        """Names of functions and classes defined in this scope."""
        names = set()
        for n in self._walk():
            if n.type in ("function_definition", "class_definition"):
                name = n.child_by_field_name("name")
                if name is not None:
                    names.add(node_text(name))
        return frozenset(names)

    def text(self) -> str:
        return "\n".join(node_text(n) for n in self.nodes)

    def assignments(self) -> list[tuple[str, frozenset[str]]]:
        """(assigned name, identifiers on the right-hand side) for simple `x = …` statements."""
        found = []
        for n in self._walk():
            if n.type != "assignment":
                continue
            left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
            if left is not None and right is not None and left.type == "identifier":
                rhs = frozenset(node_text(d) for d in descendants(right) if d.type == "identifier")
                found.append((node_text(left), rhs))
        return found

    def function(self, name: str) -> Node | None:
        """The definition of function ``name`` in this scope, if any."""
        for n in self._walk():
            if n.type == "function_definition":
                ident = n.child_by_field_name("name")
                if ident is not None and node_text(ident) == name:
                    return n
        return None

    def class_definition(self, name: str) -> Node | None:
        """The definition of class ``name`` in this scope, if any."""
        for n in self._walk():
            if n.type == "class_definition":
                ident = n.child_by_field_name("name")
                if ident is not None and node_text(ident) == name:
                    return n
        return None

    def function_spans(self) -> list[tuple[int, int]]:
        """(first line, last line) of every function in this scope."""
        return [
            (start_line(n), end_line(n)) for n in self._walk() if n.type == "function_definition"
        ]

    def loops_containing(self, line: int) -> bool:
        return any(
            n.type in ("for_statement", "while_statement") and start_line(n) <= line <= end_line(n)
            for n in self._walk()
        )

    def _walk(self) -> Iterator[Node]:
        for root in self.nodes:
            yield from descendants(root)


def scope_of(code: str) -> Scope:
    return Scope((parse(code).root_node,))


# ---------------------------------------------------------------- test functions


@dataclass(frozen=True)
class TestFunction:
    """A pytest test function and what it feeds into the code under test."""

    __test__ = False  # not itself a pytest test

    path: str
    qualified_name: str
    line: int
    callees: tuple[str, ...]  # e.g. ("validate_username", "pytest.raises")
    strings: tuple[str, ...]  # string literal contents, e.g. ("",) or ("   ",)
    numbers: tuple[float, ...]  # numeric literals, sign included
    uses_none: bool
    empty_collection: bool  # an empty list/dict/tuple/set literal is used, e.g. total([])
    body_identifiers: frozenset[str]  # identifiers in the body (the name itself excluded)
    expected_exceptions: tuple[str, ...]  # from pytest.raises(X) / self.assertRaises(X)
    tokens: tuple[str, ...] = field(compare=False, repr=False)
    body_tokens: tuple[str, ...] = field(default=(), compare=False, repr=False)  # name excluded
    skipped: bool = False  # @skip / @skipif / @xfail, or pytest.skip() in the body
    has_expectation: bool = True  # an assert, pytest.raises, self.assert*, mock.assert_*
    singleton_collection: bool = False  # a one-element list/tuple/set literal, e.g. median([3])
    parameters: tuple[str, ...] = ()  # pytest fixtures the test asks for

    def calls(self, function: str) -> bool:
        return any(c == function or c.endswith("." + function) for c in self.callees)


def find_test_functions(path: str, code: str) -> list[TestFunction]:
    found: list[TestFunction] = []
    for symbol in index_symbols(parse(code)):
        if symbol.kind == "class" or not symbol.name.startswith("test"):
            continue
        body = symbol.node.child_by_field_name("body")
        if body is None:
            continue
        facts = extract_facts(body)
        decorators = _decorators(symbol.node)
        # Inputs may come from decorators too: @pytest.mark.parametrize("v", [None, ""]).
        inputs = [body, *decorators]
        callees = tuple(c.callee for c in facts.calls)
        found.append(
            TestFunction(
                path=path,
                qualified_name=symbol.qualified_name,
                line=symbol.start_line,
                callees=callees,
                strings=tuple(s for n in inputs for s in _strings(n)),
                numbers=tuple(v for n in inputs for v in _numbers(n)),
                uses_none=any(d.type == "none" for n in inputs for d in descendants(n)),
                empty_collection=any(
                    d.type in _COLLECTIONS and not d.named_children
                    for n in inputs
                    for d in descendants(n)
                ),
                body_identifiers=facts.identifiers,
                expected_exceptions=tuple(
                    _first_argument(c) for c in facts.calls if c.callee.lower().endswith("raises")
                ),
                tokens=structural_tokens(symbol.node),
                body_tokens=structural_tokens(body),
                skipped=any(_SKIP_MARK.search(node_text(d)) for d in decorators)
                or any(c.endswith(_SKIP_CALLS) for c in callees),
                has_expectation=any(d.type == "assert_statement" for d in descendants(body))
                or any(_is_expectation(c) for c in callees),
                singleton_collection=any(
                    d.type in ("list", "tuple", "set") and len(d.named_children) == 1
                    for n in inputs
                    for d in descendants(n)
                ),
                parameters=tuple(
                    p
                    for p in function_parameters(symbol.node)
                    if p not in _parametrized(decorators)
                ),
            )
        )
    return found


_PARAMETRIZE = re.compile(r"parametrize\(\s*[\"']([^\"']+)[\"']")


def _parametrized(decorators: list[Node]) -> set[str]:
    """Argument names a `@pytest.mark.parametrize("a, b", …)` supplies (they are not fixtures)."""
    names: set[str] = set()
    for decorator in decorators:
        for group in _PARAMETRIZE.findall(node_text(decorator)):
            names |= {n.strip() for n in group.split(",") if n.strip()}
    return names


# Decorators and calls that keep a test from demonstrating anything.
_SKIP_MARK = re.compile(r"\b(skip|skipif|skipIf|skipUnless|xfail|expectedFailure)\b")
_SKIP_CALLS = ("pytest.skip", "skipTest", "pytest.xfail")


def _is_expectation(callee: str) -> bool:
    last = callee.split(".")[-1].lower()
    return (
        last.startswith("assert")
        or last in ("raises", "warns", "deprecated_call", "fail")
        or last.startswith("assert_")
    )


def changed_test_functions(after: dict[str, str], before: dict[str, str]) -> list[TestFunction]:
    """Test functions that did not exist, or changed, between the two versions of the files."""
    changed: list[TestFunction] = []
    for path, code in after.items():
        previous = find_test_functions(path, before.get(path, ""))
        current = find_test_functions(path, code)
        old = {t.qualified_name: t.tokens for t in previous}
        # A test that only got a new name (same body, old name gone) is not a new test.
        names_now = {t.qualified_name for t in current}
        renamed_from = {t.body_tokens for t in previous if t.qualified_name not in names_now}
        changed += [
            t
            for t in current
            if old.get(t.qualified_name) != t.tokens
            and not (t.qualified_name not in old and t.body_tokens in renamed_from)
        ]
    return changed


# ---------------------------------------------------------------- functions and calls


def function_parameters(definition: Node) -> list[str]:
    """Parameter names of a function definition, in order (`self`/`cls` excluded)."""
    params = definition.child_by_field_name("parameters")
    names: list[str] = []
    for p in params.named_children if params is not None else []:
        ident = (
            p
            if p.type == "identifier"
            else next((c for c in p.named_children if c.type == "identifier"), None)
        )
        if ident is not None and node_text(ident) not in ("self", "cls"):
            names.append(node_text(ident))
    return names


_CONSTRAINED = re.compile(
    r"\bField\([^)]*\b(gt|ge|lt|le|min_length|max_length|pattern|regex|multiple_of)\s*=|"
    r"\b(Positive|Negative|NonNegative|NonPositive)(Int|Float)\b|\bcon(int|float|str|list|decimal)\("
)
_FIELD_VALIDATOR = re.compile(r"@(?:field_validator|validator)\(\s*[\"'](\w+)[\"']")


def model_constraint(model: Node, field_name: str) -> str | None:
    """The pydantic constraint on a model field, if any: `amount: float = Field(gt=0)`.

    Counts a constrained annotation/default (`Field(gt=0)`, `PositiveInt`, `conint(ge=1)`) or a
    `@field_validator("amount")` / `@validator("amount")` method.
    """
    body = model.child_by_field_name("body")
    if body is None:
        return None
    for statement in body.named_children:
        text = node_text(statement)
        target = re.match(rf"\s*{re.escape(field_name)}\s*:", text)
        if target and _CONSTRAINED.search(text):
            return normalized_text(statement)
        for validated in _FIELD_VALIDATOR.findall(text):
            if validated == field_name:
                return f"@field_validator('{field_name}')"
    return None


_ROUTE = re.compile(r"\.(?:route|get|post|put|patch|delete|api_route)\(\s*[rf]?[\"']([^\"']+)")


def route_paths(definition: Node) -> list[str]:
    """Static URL prefixes a web handler serves: @app.get("/orders/<int:id>") → "/orders/"."""
    paths = []
    for decorator in _decorators(definition):
        match = _ROUTE.search(node_text(decorator))
        if match:
            paths.append(re.split(r"[<{]", match.group(1))[0])
    return paths


def call_arguments(call_text: str, callee: str) -> list[tuple[str | None, str]]:
    """(keyword or None, argument text) for a call's top-level arguments."""
    inside = call_text[len(callee) :].strip()
    if not inside.startswith("(") or not inside.endswith(")"):
        return []
    args, depth, current = [], 0, ""
    for ch in inside[1:-1]:
        if ch == "," and depth == 0:
            args.append(current.strip())
            current = ""
            continue
        depth += ch in "([{"
        depth -= ch in ")]}"
        current += ch
    if current.strip():
        args.append(current.strip())
    parsed: list[tuple[str | None, str]] = []
    for a in args:
        key, sep, value = a.partition("=")
        if sep and key.strip().isidentifier() and not value.startswith("="):
            parsed.append((key.strip(), value.strip()))
        else:
            parsed.append((None, a))
    return parsed


# ---------------------------------------------------------------- helpers

_COLLECTIONS = frozenset({"list", "dictionary", "tuple", "set"})


def _decorators(definition: Node) -> list[Node]:
    parent = definition.parent
    if parent is None or parent.type != "decorated_definition":
        return []
    return [c for c in parent.named_children if c.type == "decorator"]


def _branch(node: Node) -> tuple[BranchCondition, ...]:
    """Conditions of the if/elif/else branches enclosing ``node``, innermost first."""
    found: list[BranchCondition] = []
    child, parent = node, node.parent
    while parent is not None:
        if parent.type in ("if_statement", "elif_clause"):
            consequence = parent.child_by_field_name("consequence")
            condition = parent.child_by_field_name("condition")
            if condition is not None and consequence is not None and consequence.id == child.id:
                found.append(BranchCondition(condition_fact(condition, "if"), negated=False))
        elif parent.type == "else_clause" and parent.parent is not None:
            condition = parent.parent.child_by_field_name("condition")
            if condition is not None:
                found.append(BranchCondition(condition_fact(condition, "if"), negated=True))
        elif parent.type == "except_clause":
            found.append(BranchCondition(_except_condition(parent), negated=False))
        child, parent = parent, parent.parent
    return tuple(found)


def _except_condition(clause: Node) -> Condition:
    """An except clause as a branch condition: "`json.loads(body)` failed with E".

    Its identifiers are the exception's and those of the protected try body, so "invalid JSON"
    matches `except json.JSONDecodeError` around `json.loads(request.body)`.
    """
    names = {node_text(n) for n in descendants(clause) if n.type == "identifier"}
    block = next((c for c in clause.named_children if c.type == "block"), None)
    if block is not None:
        names -= {node_text(n) for n in descendants(block) if n.type == "identifier"}
    try_node = clause.parent
    body = try_node.child_by_field_name("body") if try_node is not None else None
    if body is not None:
        names |= {node_text(n) for n in descendants(body) if n.type == "identifier"}
    header = normalized_text(clause).split(":")[0]
    return Condition("condition", header, start_line(clause), "if", frozenset(names))


# Exceptions web frameworks turn into a status: `raise Http404`, `raise NotFound()`.
_EXCEPTION_STATUS = {
    "Http404": 404,
    "NotFound": 404,
    "BadRequest": 400,
    "SuspiciousOperation": 400,
    "Unauthorized": 401,
    "Forbidden": 403,
    "PermissionDenied": 403,
    "MethodNotAllowed": 405,
    "Conflict": 409,
    "Gone": 410,
    "UnprocessableEntity": 422,
}
# Django response classes that carry their status in the name.
_RESPONSE_CLASSES = {
    "HttpResponseBadRequest": 400,
    "HttpResponseForbidden": 403,
    "HttpResponseNotFound": 404,
    "HttpResponseNotAllowed": 405,
    "HttpResponseGone": 410,
    "HttpResponseServerError": 500,
    "HttpResponseRedirect": 302,
    "HttpResponsePermanentRedirect": 301,
    "HttpResponseNotModified": 304,
}
_HTTP_STATUS_NAMES = {s.name: s.value for s in HTTPStatus}
_STATUS_CONSTANT = re.compile(r"\bHTTP_(\d{3})_")  # DRF / Starlette: status.HTTP_404_NOT_FOUND
_ERROR_HANDLER = re.compile(r"\.(?:errorhandler|exception_handler)\(\s*([\w.]+)")


def _status_names(node: Node) -> list[int]:
    codes = []
    for n in descendants(node):
        if n.type == "attribute":
            text = node_text(n)
            match = _STATUS_CONSTANT.search(text)
            if match and int(match.group(1)) in HTTP_STATUS:
                codes.append(int(match.group(1)))
            elif text.split(".")[-2:-1] == ["HTTPStatus"]:
                code = _HTTP_STATUS_NAMES.get(text.split(".")[-1])
                if code in HTTP_STATUS:
                    codes.append(code)
        elif n.type == "identifier" and node_text(n) in _RESPONSE_CLASSES:
            codes.append(_RESPONSE_CLASSES[node_text(n)])
    return [c for c in codes if c is not None]


def _raised_name(node: Node) -> str:
    """`raise NotFound("x")` / `raise errors.NotFound` → "NotFound"."""
    if not node.named_children:
        return ""
    value = node.named_children[0]
    if value.type == "call":
        return _callee_name(value).split(".")[-1]
    return node_text(value).split(".")[-1]


def _unreachable(node: Node) -> bool:
    """A statement after an unconditional return/raise/continue/break in the same block."""
    child, parent = node, node.parent
    while parent is not None and parent.type != "function_definition":
        if parent.type in ("block", "module"):
            for sibling in parent.named_children:
                if sibling.id == child.id:
                    break
                if sibling.type in _EXITS:
                    return True
        child, parent = parent, parent.parent
    return False


_EXITS = frozenset({"return_statement", "raise_statement", "continue_statement", "break_statement"})


def error_handler_codes(module: "Scope") -> dict[str, int]:
    """Exceptions an `@app.errorhandler(E)` function turns into a status, e.g. {"NotFound": 404}."""
    codes: dict[str, int] = {}
    for node in module._walk():
        if node.type != "function_definition":
            continue
        for decorator in _decorators(node):
            match = _ERROR_HANDLER.search(node_text(decorator))
            if not match:
                continue
            returned = Scope((node,)).responses()
            if returned:
                codes[match.group(1).split(".")[-1]] = returned[0].code
    return codes


def _status_literals(node: Node) -> list[int]:
    codes = []
    for n in descendants(node):
        if n.type == "integer":
            try:
                value = int(node_text(n))
            except ValueError:
                continue
            if value in HTTP_STATUS:
                codes.append(value)
    return codes


def _callee_name(call: Node) -> str:
    function = call.child_by_field_name("function")
    return node_text(function) if function is not None else ""


def _strings(node: Node) -> Iterator[str]:
    for n in descendants(node):
        if n.type == "string":
            content = "".join(node_text(c) for c in n.named_children if c.type == "string_content")
            yield content


def _numbers(node: Node) -> Iterator[float]:
    for n in descendants(node):
        if n.type in ("integer", "float"):
            try:
                value = float(node_text(n).replace("_", ""))
            except ValueError:
                continue
            parent = n.parent
            negative = (
                parent is not None
                and parent.type == "unary_operator"
                and node_text(parent).lstrip().startswith("-")
            )
            yield -value if negative else value


def _first_argument(call: Call) -> str:
    inside = call.text[len(call.callee) :].strip()
    return inside[1:].split(",")[0].rstrip(")").strip() if inside.startswith("(") else ""
