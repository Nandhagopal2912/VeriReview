"""Line-level comparison with ``difflib`` (plan §11: simple textual comparison / baseline)."""

import difflib
from collections.abc import Hashable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Change:
    """One diff region: before lines [b_start, b_end) → after lines [a_start, a_end), 0-based."""

    b_start: int
    b_end: int
    a_start: int
    a_end: int

    def touches(self, first: int, last: int) -> bool:
        """Does the change touch 1-based before-lines ``first..last`` (inserts at a gap count)?"""
        if self.b_start == self.b_end:  # pure insertion before line b_start + 1
            return first - 1 <= self.b_start <= last
        return self.b_start < last and self.b_end >= first


def changes(before: str, after: str) -> list[Change]:
    matcher = difflib.SequenceMatcher(None, before.split("\n"), after.split("\n"), autojunk=False)
    return [
        Change(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"
    ]


def line_mapping(before: str, after: str) -> dict[int, int]:
    """1-based before-line → after-line for every line the diff leaves unchanged."""
    matcher = difflib.SequenceMatcher(None, before.split("\n"), after.split("\n"), autojunk=False)
    mapping: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapping[block.a + offset + 1] = block.b + offset + 1
    return mapping


def similarity(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    """Ratio in [0, 1] of matching elements (difflib); 1.0 for two empty sequences."""
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
