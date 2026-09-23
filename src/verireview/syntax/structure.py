"""Structural comparison that ignores comments, docstrings and formatting.

Two versions of a function are *structurally equal* when their syntax trees match after
dropping comments and docstrings. This separates "the code changed" from "someone added a
comment that mentions the fix" (the lexical false positives in the dev set).
"""

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass

from tree_sitter import Node

from verireview.syntax.facts import CodeFacts, Fact
from verireview.syntax.parser import node_text, parse

_BLOCK_OWNERS = frozenset({"function_definition", "class_definition", "module"})


def structural_tokens(root: Node) -> tuple[str, ...]:
    """Leaf tokens of ``root`` without comments and docstrings (whitespace is never a token)."""
    return tuple(_tokens(root))


def _tokens(node: Node) -> Iterator[str]:
    if node.type == "comment" or _is_docstring(node):
        return
    if node.child_count == 0:
        yield f"{node.type}:{node_text(node)}" if node.is_named else node.type
        return
    for child in node.children:
        yield from _tokens(child)


def code_only(source: str) -> str:
    """``source`` with comments and docstrings blanked out (spaces); line numbers are unchanged.

    Used by the code model (Phase 7) so that a comment repeating the reviewer's words cannot
    count as code, the lexical trap measured in Phase 6.
    """
    data = bytearray(source.encode("utf-8"))
    stack = [parse(source).root_node]
    while stack:
        node = stack.pop()
        if node.type == "comment" or _is_docstring(node):
            for i in range(node.start_byte, node.end_byte):
                if data[i] not in b"\r\n":
                    data[i] = 0x20
            continue
        stack.extend(node.children)
    return data.decode("utf-8")


def _is_docstring(node: Node) -> bool:
    """A string expression that is the first statement of a module, class or function body."""
    if node.type != "expression_statement" or len(node.named_children) != 1:
        return False
    if node.named_children[0].type != "string":
        return False
    parent = node.parent
    if parent is None:
        return False
    owner = parent if parent.type == "module" else parent.parent
    if owner is None or owner.type not in _BLOCK_OWNERS:
        return False
    first = next((c for c in parent.named_children if c.type != "comment"), None)
    return first is not None and first.id == node.id


@dataclass(frozen=True)
class FactDiff:
    added: tuple[Fact, ...]
    removed: tuple[Fact, ...]

    @property
    def empty(self) -> bool:
        return not self.added and not self.removed


def diff_facts(before: CodeFacts, after: CodeFacts) -> FactDiff:
    """Facts that appear more often after (added) or before (removed), matched by kind + text.

    Matching ignores position, so code that merely moved is not reported as added/removed.
    """
    before_counts = Counter(f.key for f in before.all())
    after_counts = Counter(f.key for f in after.all())
    added = _take(after.all(), after_counts - before_counts)
    removed = _take(before.all(), before_counts - after_counts)
    return FactDiff(added=tuple(added), removed=tuple(removed))


def _take(facts: list[Fact], wanted: Counter[tuple[str, str]]) -> list[Fact]:
    remaining = Counter(wanted)
    picked = []
    for fact in sorted(facts, key=lambda f: f.line):
        if remaining[fact.key] > 0:
            picked.append(fact)
            remaining[fact.key] -= 1
    return picked
