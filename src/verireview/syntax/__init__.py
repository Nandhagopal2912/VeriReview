"""Tree-sitter structural analysis: symbols, calls, conditions (Phase 3).

Named ``syntax`` rather than ``ast`` to avoid shadowing the stdlib ``ast`` module.
"""

from verireview.syntax.facts import (
    Call,
    CodeFacts,
    Condition,
    Fact,
    Handler,
    Raise,
    Return,
    extract_facts,
)
from verireview.syntax.location import ResolutionMethod, TargetResolution, resolve_target
from verireview.syntax.parser import parse
from verireview.syntax.structure import FactDiff, code_only, diff_facts, structural_tokens
from verireview.syntax.symbols import Symbol, enclosing_symbol, find_symbol, index_symbols

__all__ = [
    "Call",
    "CodeFacts",
    "Condition",
    "Fact",
    "FactDiff",
    "Handler",
    "Raise",
    "ResolutionMethod",
    "Return",
    "Symbol",
    "TargetResolution",
    "code_only",
    "diff_facts",
    "enclosing_symbol",
    "extract_facts",
    "find_symbol",
    "index_symbols",
    "parse",
    "resolve_target",
    "structural_tokens",
]
