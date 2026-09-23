"""Code-only view of a change, for the code model (Phase 7).

Phase 6 showed that the main trap for similarity is a comment repeating the reviewer's words
(`# TODO: validate username`). The code model therefore sees only *code*: the added lines with
comments and docstrings blanked out (Tree-sitter), split into chunks of consecutive added lines.
Each chunk keeps its location, so evidence about it can cite file:line like any other evidence.

A change that only adds comments yields no chunks at all.
"""

import difflib
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass

from verireview.contracts import ReviewCase
from verireview.diff import DiffParseError, parse_unified_diff
from verireview.syntax import code_only


@dataclass(frozen=True)
class CodeChunk:
    file: str
    line_start: int  # 1-based, in the file after the change
    line_end: int
    text: str  # code only, dedented, blank lines dropped


def change_chunks(case: ReviewCase) -> list[CodeChunk]:
    """Added code in the commented file, then in each changed test file (sorted by path)."""
    chunks: list[CodeChunk] = []
    if case.after_code is not None:
        runs = _runs(_added_after_lines(case.unified_diff))
        chunks += _chunks(case.file_path, case.after_code, runs)
    for path, after in sorted(case.test_files.items()):
        before = case.test_files_before.get(path, "")
        chunks += _chunks(path, after, _inserted_runs(before, after))
    return chunks


def code_change_text(case: ReviewCase) -> str:
    """All added code (no comments, no docstrings) as one text: the Phase 7 'code' view."""
    return "\n".join(c.text for c in change_chunks(case))


def _added_after_lines(unified_diff: str) -> list[int]:
    try:
        files = parse_unified_diff(unified_diff)
    except DiffParseError:
        return []
    return sorted({line.number for f in files for h in f.hunks for line in h.added})


def _runs(numbers: Iterable[int]) -> list[tuple[int, int]]:
    """Consecutive line numbers grouped into (first, last) runs."""
    runs: list[tuple[int, int]] = []
    for n in numbers:
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    return runs


def _inserted_runs(before: str, after: str) -> list[tuple[int, int]]:
    matcher = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines(), autojunk=False)
    return [
        (j1 + 1, j2)
        for tag, _, _, j1, j2 in matcher.get_opcodes()
        if tag in ("insert", "replace") and j2 > j1
    ]


def _chunks(path: str, source: str, runs: list[tuple[int, int]]) -> list[CodeChunk]:
    if not runs:
        return []
    lines = code_only(source).splitlines()
    chunks = []
    for first, last in runs:
        kept = [(n, lines[n - 1].rstrip()) for n in range(first, last + 1) if lines[n - 1].strip()]
        if kept:  # a run of comments / docstring lines is not code
            text = textwrap.dedent("\n".join(line for _, line in kept))
            chunks.append(CodeChunk(path, line_start=kept[0][0], line_end=kept[-1][0], text=text))
    return chunks
