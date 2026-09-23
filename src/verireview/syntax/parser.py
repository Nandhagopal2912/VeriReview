"""Tree-sitter parsing for Python.

Tree-sitter never raises on invalid code: it produces ``ERROR``/``MISSING`` nodes and sets
``has_error``. Callers treat that as a reliability signal, not a failure.
"""

from functools import lru_cache

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Tree


@lru_cache(maxsize=1)
def python_language() -> Language:
    return Language(tree_sitter_python.language())


def parse(code: str) -> Tree:
    # A Parser is cheap and not thread-safe, so one per call.
    return Parser(python_language()).parse(code.encode("utf-8"))


def node_text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", errors="replace")


def start_line(node: Node) -> int:
    """1-based first line of ``node``."""
    return node.start_point.row + 1


def end_line(node: Node) -> int:
    """1-based last line of ``node`` (a node ending at column 0 ends on the previous line)."""
    row = node.end_point.row
    if node.end_point.column == 0 and row > node.start_point.row:
        row -= 1
    return row + 1
