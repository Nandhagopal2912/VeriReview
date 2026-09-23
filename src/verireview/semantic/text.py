"""Text views of a case for similarity baselines (Phase 6).

- comment_text: the reviewer's comment, cleaned (quotes, links, code blocks removed), plus any
  suggestion block
- change_text: the lines the developer *added* after the comment, in the commented file and in
  changed test files

Comments and docstrings are deliberately kept: these baselines see what a text-similarity
approach sees, and that is exactly what the ablation study (plan §21) measures.
"""

import difflib
import re

from verireview.contracts import ReviewCase
from verireview.diff import DiffParseError, parse_unified_diff
from verireview.requirements.text import prepare

_IDENT_PART = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "when",
        "while",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "please",
        "can",
        "could",
        "should",
        "would",
        "will",
        "may",
        "might",
        "must",
        "do",
        "does",
        "did",
        "done",
        "not",
        "no",
        "yes",
        "so",
        "than",
        "too",
        "very",
        "just",
        "also",
        "into",
        "out",
        "up",
        "self",
        "def",
        "return",
        "pass",
        "none",
        "true",
        "false",
        "import",
        "class",
    ]
)


def comment_text(case: ReviewCase) -> str:
    prepared = prepare(case.thread.root.body)
    return " ".join([prepared.text, *prepared.suggestions]).strip()


def change_text(case: ReviewCase) -> str:
    """Added lines (code + comments) in the commented file and in changed test files."""
    added = _added_lines(case.unified_diff)
    for path, after in sorted(case.test_files.items()):
        before = case.test_files_before.get(path, "")
        added += _added_between(before, after)
    return "\n".join(line for line in added if line.strip())


def words(text: str) -> list[str]:
    """Lower-case content words; identifiers split (`total_price`, `getUser` → words)."""
    out: list[str] = []
    for token in _TOKEN.findall(text):
        for part in token.split("_"):
            out += [p.lower() for p in _IDENT_PART.findall(part)]
    return [w for w in out if len(w) > 1 and w not in STOPWORDS]


def _added_lines(unified_diff: str) -> list[str]:
    try:
        files = parse_unified_diff(unified_diff)
    except DiffParseError:
        return []
    return [line.text for f in files for h in f.hunks for line in h.added]


def _added_between(before: str, after: str) -> list[str]:
    diff = difflib.ndiff(before.splitlines(), after.splitlines())
    return [line[2:] for line in diff if line.startswith("+ ")]
