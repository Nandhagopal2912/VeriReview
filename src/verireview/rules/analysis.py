"""Structural queries the rules are built on (all over Tree-sitter nodes, never raw text).

- ``guards``: if / elif / assert conditions, with what their branch does (raise? return?)
- ``handlers``: except clauses, with what they protect and what their body does
- ``responses``: status codes produced by returns / aborts, with the branch conditions above them
- ``test_functions``: test functions, with the calls and literal inputs they use
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
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
                    )
                )
            elif node.type == "assert_statement" and node.named_children:
                cond = condition_fact(node.named_children[0], "assert")
                found.append(Guard(cond, start_line(node), end_line(node), "assert", (), ()))
        return sorted(found, key=lambda g: g.line)

    def handlers(self) -> list[HandlerInfo]:
        found: list[HandlerInfo] = []
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

    def responses(self) -> list[StatusSite]:
        """HTTP status codes produced by returns or abort-like calls, with their branch."""
        sites: list[StatusSite] = []
        for node in self._walk():
            status_call = node.type == "call" and _callee_name(node).endswith(_STATUS_CALLEES)
            if node.type != "return_statement" and not status_call:
                continue
            for code in _status_literals(node):
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
    body_identifiers: frozenset[str]  # identifiers in the body (the name itself excluded)
    expected_exceptions: tuple[str, ...]  # from pytest.raises(X)
    tokens: tuple[str, ...] = field(compare=False, repr=False)

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
        found.append(
            TestFunction(
                path=path,
                qualified_name=symbol.qualified_name,
                line=symbol.start_line,
                callees=tuple(c.callee for c in facts.calls),
                strings=tuple(_strings(body)),
                numbers=tuple(_numbers(body)),
                uses_none=any(n.type == "none" for n in descendants(body)),
                body_identifiers=facts.identifiers,
                expected_exceptions=tuple(
                    _first_argument(c) for c in facts.calls if c.callee.endswith("raises")
                ),
                tokens=structural_tokens(symbol.node),
            )
        )
    return found


def changed_test_functions(after: dict[str, str], before: dict[str, str]) -> list[TestFunction]:
    """Test functions that did not exist, or changed, between the two versions of the files."""
    changed: list[TestFunction] = []
    for path, code in after.items():
        old = {t.qualified_name: t.tokens for t in find_test_functions(path, before.get(path, ""))}
        changed += [
            t for t in find_test_functions(path, code) if old.get(t.qualified_name) != t.tokens
        ]
    return changed


# ---------------------------------------------------------------- helpers


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
        child, parent = parent, parent.parent
    return tuple(found)


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
