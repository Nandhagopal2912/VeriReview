"""Symbol index: every function, method and class, with qualified names and line ranges."""

from dataclasses import dataclass, field
from typing import Literal

from tree_sitter import Node, Tree

from verireview.syntax.parser import end_line, node_text, start_line

SymbolKind = Literal["function", "method", "class"]


@dataclass(frozen=True)
class Symbol:
    name: str
    qualified_name: str  # "Class.method", "outer.inner"
    kind: SymbolKind
    start_line: int  # 1-based; includes decorators
    end_line: int
    node: Node = field(compare=False, repr=False)  # the function/class definition itself

    def contains(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line

    @property
    def span(self) -> int:
        return self.end_line - self.start_line


def index_symbols(tree: Tree) -> list[Symbol]:
    """All definitions in source order (outer before inner)."""
    symbols: list[Symbol] = []
    _walk(tree.root_node, prefix="", in_class=False, out=symbols)
    return symbols


def enclosing_symbol(symbols: list[Symbol], line: int) -> Symbol | None:
    """Innermost symbol containing ``line``, or None at module level."""
    containing = [s for s in symbols if s.contains(line)]
    return min(containing, key=lambda s: s.span) if containing else None


def find_symbol(symbols: list[Symbol], qualified_name: str) -> Symbol | None:
    return next((s for s in symbols if s.qualified_name == qualified_name), None)


def _walk(node: Node, prefix: str, in_class: bool, out: list[Symbol]) -> None:
    for child in node.named_children:
        outer = child
        definition = child
        if child.type == "decorated_definition":
            inner = child.child_by_field_name("definition")
            if inner is None:
                continue
            definition = inner
        if definition.type not in ("function_definition", "class_definition"):
            _walk(child, prefix, in_class, out)
            continue
        name_node = definition.child_by_field_name("name")
        if name_node is None:  # incomplete code
            continue
        name = node_text(name_node)
        qualified = f"{prefix}.{name}" if prefix else name
        is_class = definition.type == "class_definition"
        kind: SymbolKind = "class" if is_class else ("method" if in_class else "function")
        out.append(
            Symbol(
                name=name,
                qualified_name=qualified,
                kind=kind,
                start_line=start_line(outer),
                end_line=end_line(outer),
                node=definition,
            )
        )
        body = definition.child_by_field_name("body")
        if body is not None:
            _walk(body, qualified, in_class=is_class, out=out)
