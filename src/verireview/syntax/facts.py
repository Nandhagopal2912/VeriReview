"""Structural facts extracted from a syntax subtree (plan §11: calls, conditions, identifiers…).

Facts are what Phase 5 rules reason about ("is there a None-check on `username` before the
`insert` call?"). Text is whitespace-normalised so formatting changes don't count as changes.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from tree_sitter import Node

from verireview.syntax.parser import node_text, start_line

ConditionKind = Literal["if", "elif", "while", "assert", "ternary"]
FactKind = Literal["call", "condition", "raise", "handler", "return"]

_EMPTY_LITERALS = frozenset({'""', "''", "[]", "{}", "()", "0"})


@dataclass(frozen=True)
class Fact:
    kind: FactKind
    text: str  # normalised source text of the construct
    line: int  # 1-based

    @property
    def key(self) -> tuple[str, str]:
        """Identity for structural diffs: same kind and same code, wherever it sits."""
        return (self.kind, self.text)


@dataclass(frozen=True)
class Call(Fact):
    callee: str = ""  # e.g. "database.insert", "ValueError"


@dataclass(frozen=True)
class Condition(Fact):
    condition_kind: ConditionKind = "if"
    identifiers: frozenset[str] = frozenset()
    checks_none: bool = False  # `x is None`, `x is not None`, `x == None`
    checks_empty: bool = False  # `not x`, `len(x) == 0`, `x == ""`


@dataclass(frozen=True)
class Raise(Fact):
    exception: str | None = None  # None for a bare `raise`


@dataclass(frozen=True)
class Handler(Fact):
    exceptions: tuple[str, ...] = ()  # () for a bare `except:`
    swallows: bool = False  # body does nothing (only pass / ... / docstring)
    reraises: bool = False  # body contains a raise


@dataclass(frozen=True)
class Return(Fact):
    value: str = ""


@dataclass(frozen=True)
class CodeFacts:
    calls: tuple[Call, ...] = ()
    conditions: tuple[Condition, ...] = ()
    raises: tuple[Raise, ...] = ()
    handlers: tuple[Handler, ...] = ()
    returns: tuple[Return, ...] = ()
    identifiers: frozenset[str] = field(default_factory=frozenset)

    def all(self) -> list[Fact]:
        return [*self.calls, *self.conditions, *self.raises, *self.handlers, *self.returns]

    def merged(self, other: "CodeFacts") -> "CodeFacts":
        return CodeFacts(
            calls=self.calls + other.calls,
            conditions=self.conditions + other.conditions,
            raises=self.raises + other.raises,
            handlers=self.handlers + other.handlers,
            returns=self.returns + other.returns,
            identifiers=self.identifiers | other.identifiers,
        )


def extract_facts(root: Node) -> CodeFacts:
    """Facts in ``root``'s subtree (nested definitions included: they are part of the code)."""
    calls: list[Call] = []
    conditions: list[Condition] = []
    raises: list[Raise] = []
    handlers: list[Handler] = []
    returns: list[Return] = []
    identifiers: set[str] = set()

    for node in descendants(root):
        match node.type:
            case "identifier":
                identifiers.add(node_text(node))
            case "call":
                function = node.child_by_field_name("function")
                calls.append(
                    Call("call", normalized_text(node), start_line(node), callee=_callee(function))
                )
            case "if_statement" | "elif_clause" | "while_statement":
                condition = node.child_by_field_name("condition")
                if condition is not None:
                    kind: ConditionKind = (
                        "elif"
                        if node.type == "elif_clause"
                        else "while"
                        if node.type == "while_statement"
                        else "if"
                    )
                    conditions.append(condition_fact(condition, kind))
            case "assert_statement":
                if node.named_children:
                    conditions.append(condition_fact(node.named_children[0], "assert"))
            case "conditional_expression":
                if len(node.named_children) >= 2:
                    conditions.append(condition_fact(node.named_children[1], "ternary"))
            case "raise_statement":
                raises.append(
                    Raise("raise", normalized_text(node), start_line(node), exception=_raised(node))
                )
            case "except_clause":
                handlers.append(handler_fact(node))
            case "return_statement":
                value = node.named_children[0] if node.named_children else None
                returns.append(
                    Return(
                        "return",
                        normalized_text(node),
                        start_line(node),
                        value=normalized_text(value) if value else "",
                    )
                )

    return CodeFacts(
        calls=tuple(calls),
        conditions=tuple(conditions),
        raises=tuple(raises),
        handlers=tuple(handlers),
        returns=tuple(returns),
        identifiers=frozenset(identifiers),
    )


def descendants(root: Node) -> Iterator[Node]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def normalized_text(node: Node) -> str:
    return " ".join(node_text(node).split())


def _callee(function: Node | None) -> str:
    return normalized_text(function) if function is not None else ""


def condition_fact(node: Node, kind: ConditionKind) -> Condition:
    names = {node_text(n) for n in descendants(node) if n.type == "identifier"}
    return Condition(
        "condition",
        normalized_text(node),
        start_line(node),
        condition_kind=kind,
        identifiers=frozenset(names),
        checks_none=_checks_none(node),
        checks_empty=_checks_empty(node),
    )


def _checks_none(node: Node) -> bool:
    for n in descendants(node):
        if n.type == "comparison_operator" and any(c.type == "none" for c in n.named_children):
            return True
    return False


def _checks_empty(node: Node) -> bool:
    for n in descendants(node):
        if n.type == "not_operator":
            return True
        if n.type == "comparison_operator":
            operands = [normalized_text(c) for c in n.named_children]
            if any(o in _EMPTY_LITERALS for o in operands) or any(
                o.startswith("len(") for o in operands
            ):
                return True
    return False


def _raised(node: Node) -> str | None:
    """Exception class of `raise X(...)` / `raise X`, ignoring `from cause`; None if bare."""
    for index, child in enumerate(node.children):
        if child.is_named and node.field_name_for_child(index) != "cause":
            if child.type == "call":
                return _callee(child.child_by_field_name("function"))
            return normalized_text(child)
    return None


def handler_fact(node: Node) -> Handler:
    value = node.child_by_field_name("value")
    exceptions: tuple[str, ...] = ()
    if value is not None:
        target = value.named_children[0] if value.type == "as_pattern" else value
        items = target.named_children if target.type == "tuple" else [target]
        exceptions = tuple(normalized_text(i) for i in items)
    body = next((c for c in node.named_children if c.type == "block"), None)
    statements = [s for s in (body.named_children if body else []) if s.type != "comment"]
    swallows = all(_is_noop(s) for s in statements)
    reraises = body is not None and any(n.type == "raise_statement" for n in descendants(body))
    header = normalized_text(node).split(":", 1)[0]
    return Handler(
        "handler",
        header,
        start_line(node),
        exceptions=exceptions,
        swallows=swallows,
        reraises=reraises,
    )


def _is_noop(statement: Node) -> bool:
    if statement.type == "pass_statement":
        return True
    if statement.type == "expression_statement" and len(statement.named_children) == 1:
        return statement.named_children[0].type in ("ellipsis", "string")
    return False
