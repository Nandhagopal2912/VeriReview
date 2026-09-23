"""Code location resolution across revisions (plan §9): don't rely on line numbers alone.

Given the commented line in ``before``:

1. The enclosing symbol in ``before`` is the *target*.
2. Find the same symbol in ``after``: by qualified name, else (renamed) by the most
   structurally similar new symbol of the same kind.
3. Independently, follow the commented *line* with difflib's line mapping. If it now lives in
   a different symbol, the code was moved (e.g. extracted into a helper, the plan §9 example),
   and that symbol is relevant too.
"""

from dataclasses import dataclass
from enum import StrEnum

from verireview.diff import line_mapping, similarity
from verireview.syntax.parser import parse
from verireview.syntax.structure import structural_tokens
from verireview.syntax.symbols import Symbol, enclosing_symbol, find_symbol, index_symbols

# Below this similarity a "renamed" match is more likely a different function.
RENAME_THRESHOLD = 0.6


class ResolutionMethod(StrEnum):
    SAME_NAME = "same_name"
    RENAMED = "renamed"  # matched by structural similarity
    MODULE_LEVEL = "module_level"  # the commented line is not inside any function/class
    NOT_FOUND = "not_found"  # target symbol no longer exists (deleted or rewritten)


@dataclass(frozen=True)
class TargetResolution:
    before: Symbol | None
    after: Symbol | None
    method: ResolutionMethod
    similarity: float | None = None  # structural similarity of before vs after target
    anchor_after_line: int | None = None  # where the commented line is now, if unchanged
    moved_to: Symbol | None = None  # symbol now holding the commented line, if not `after`
    before_has_errors: bool = False
    after_has_errors: bool = False


def resolve_target(before_code: str, after_code: str, anchor_line: int) -> TargetResolution:
    before_tree, after_tree = parse(before_code), parse(after_code)
    before_symbols, after_symbols = index_symbols(before_tree), index_symbols(after_tree)
    before_errors = before_tree.root_node.has_error
    after_errors = after_tree.root_node.has_error

    anchor_after = line_mapping(before_code, after_code).get(anchor_line)
    holder = enclosing_symbol(after_symbols, anchor_after) if anchor_after else None

    target = enclosing_symbol(before_symbols, anchor_line)
    if target is None:
        return TargetResolution(
            None,
            None,
            ResolutionMethod.MODULE_LEVEL,
            anchor_after_line=anchor_after,
            before_has_errors=before_errors,
            after_has_errors=after_errors,
        )

    after, method = find_symbol(after_symbols, target.qualified_name), ResolutionMethod.SAME_NAME
    score: float | None = None
    if after is None:
        after, score = _best_rename(target, before_symbols, after_symbols)
        method = ResolutionMethod.RENAMED if after is not None else ResolutionMethod.NOT_FOUND
    else:
        score = similarity(structural_tokens(target.node), structural_tokens(after.node))

    # The commented line now lives elsewhere, unless the holder is the target itself or merely
    # *contains* it (e.g. its class).
    moved = holder is not None and (
        after is None
        or (holder.qualified_name != after.qualified_name and not holder.contains(after.start_line))
    )

    return TargetResolution(
        before=target,
        after=after,
        method=method,
        similarity=score,
        anchor_after_line=anchor_after,
        moved_to=holder if moved else None,
        before_has_errors=before_errors,
        after_has_errors=after_errors,
    )


def _best_rename(
    target: Symbol, before_symbols: list[Symbol], after_symbols: list[Symbol]
) -> tuple[Symbol | None, float | None]:
    """Most similar *new* symbol of the same kind (one whose name did not exist before)."""
    existing = {s.qualified_name for s in before_symbols}
    target_tokens = structural_tokens(target.node)
    scored = [
        (similarity(target_tokens, structural_tokens(s.node)), s)
        for s in after_symbols
        if s.kind == target.kind and s.qualified_name not in existing
    ]
    if not scored:
        return None, None
    score, best = max(scored, key=lambda pair: pair[0])
    return (best, score) if score >= RENAME_THRESHOLD else (None, score)
