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


# Positions are read by tuple index, never via ``Point.row`` / ``Point.column``: with
# tree-sitter 0.26 on Windows, the attribute getters corrupt the heap after enough calls and
# crash the process (found on a 42 KB real-world file in Phase 9b; pinned by
# tests/unit/syntax/test_parser_positions.py). Indexing the same Point is safe.


def start_line(node: Node) -> int:
    """1-based first line of ``node``."""
    return int(node.start_point[0]) + 1


def end_line(node: Node) -> int:
    """1-based last line of ``node`` (a node ending at column 0 ends on the previous line)."""
    start_row = int(node.start_point[0])
    end_row, end_column = int(node.end_point[0]), int(node.end_point[1])
    if end_column == 0 and end_row > start_row:
        end_row -= 1
    return end_row + 1
