"""Unified-diff parsing (unidiff) and textual comparison (difflib) (Phase 3)."""

from verireview.diff.textual import Change, changes, line_mapping, similarity
from verireview.diff.unified import (
    DiffHunk,
    DiffLine,
    DiffParseError,
    FileDiff,
    parse_unified_diff,
)

__all__ = [
    "Change",
    "DiffHunk",
    "DiffLine",
    "DiffParseError",
    "FileDiff",
    "changes",
    "line_mapping",
    "parse_unified_diff",
    "similarity",
]
