"""Rules for requests outside the five categories (Phase 10.1), plus GitHub suggestion blocks.

Real review requests are mostly `other` (Phase 9: 2/3 of real-world requests). Four common,
checkable shapes are verified; anything else stays inconclusive (human review):

- suggestion  a ```suggestion block is the exact expected code for the commented lines. It is
              satisfied when the suggested lines now exist where the commented ones were (the
              old lines are gone or the new ones appeared); not satisfied when the commented
              lines are still there unchanged and the suggestion is not; otherwise (changed in
              another way) inconclusive. An empty block means "delete these lines".
- removal     "remove / drop / delete this (comment, line, check…)" or "remove `x`": the
              commented lines, or the named identifier, are gone.
- docstring   "add a docstring": the target function has a docstring it did not have (or a
              changed one).
- use         "use `A` instead of `B`": `A` is now used in the target and `B` no longer is.

Lines are compared without whitespace, so re-indentation and a formatter splitting one line
over several (with a trailing comma) still match; a suggestion that only changes indentation is
compared exactly.
"""

import re

from tree_sitter import Node

from verireview.contracts import Requirement
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
    located,
    quoted_identifiers,
    unlocated,
)
from verireview.syntax.parser import node_text

_REMOVE = re.compile(
    r"^(?:please\s+|maybe\s+|just\s+|i'?d\s+|would\s+)*(?:remove|drop|delete|get rid of)\b(.*)$",
    re.I,
)
_THIS = re.compile(
    r"^\s*(?:this|that|it|these|those|the (?:above|following))?\s*"
    r"(?:comment|line|lines|paragraph|check|code|block|import|case|note|part|section|"
    r"branch|statement|assert(?:ion)?|print|debug\w*|todo)?s?\b",
    re.I,
)
_DOCSTRING = re.compile(r"\bdocstrings?\b", re.I)
_USE_INSTEAD = re.compile(
    r"\buse\s+`([^`]+)`.*?\b(?:instead of|rather than|over|not)\s+`([^`]+)`", re.I
)
_CLOSERS = re.compile(r",\s*([)\]}])")


def other_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    text = requirement.description.strip()
    if _DOCSTRING.search(text):
        return _docstring(requirement, ctx)
    if use := _USE_INSTEAD.search(text):
        return _use_instead(requirement, ctx, use.group(1), use.group(2))
    if removal := _REMOVE.match(text):
        return _removal(requirement, ctx, removal.group(1))
    return inconclusive(requirement, "No verification rule exists for this kind of request.")


# ---------------------------------------------------------------- suggestion blocks


def suggestion_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    old = _commented_lines(ctx)
    new = (requirement.suggested_code or "").split("\n")
    before, after = _target_lines(ctx)
    if not [line for line in old if line.strip()]:
        return inconclusive(requirement, "The commented lines are blank; nothing to compare.")

    exact = _normalized(old) == _normalized(new)  # only whitespace differs: compare as is
    norm = _exact if exact else _normalized
    old_block, new_block = norm(old), norm(new)
    ob, oa = _count(old_block, norm(before)), _count(old_block, norm(after))
    anchor = ctx.case.anchor_line or 1

    if not new_block:  # empty suggestion: delete the commented lines
        if oa < ob:
            return _outcome(requirement, ctx, True, "The commented lines were deleted.", anchor)
        return _outcome(requirement, ctx, False, "The lines to delete are still there.", anchor)

    nb, na = _count(new_block, norm(before)), _count(new_block, norm(after))
    if na > nb or (na >= 1 and oa < ob):
        line = _find(new_block, after, exact) or anchor
        return _outcome(requirement, ctx, True, "The suggested code is applied.", line)
    if oa >= ob and na <= nb:
        return _outcome(
            requirement,
            ctx,
            False,
            "The commented lines are unchanged and the suggestion is not applied.",
            anchor,
            version="before",
        )
    return inconclusive(
        requirement,
        "The commented lines changed, but not into the suggested code; an equivalent change "
        "needs a human to judge.",
    )


def _target_lines(ctx: RuleContext) -> tuple[list[str], list[str]]:
    """Lines of the commented function before and after (the whole file at module level), so a
    copy of the same line in another function cannot stand in for the commented one."""
    before = (ctx.case.before_code or "").split("\n")
    after = (ctx.case.after_code or "").split("\n")
    old_symbol = ctx.resolution.before
    new_symbol = ctx.resolution.after or ctx.resolution.moved_to
    if old_symbol is None or new_symbol is None:
        return before, after
    return (
        before[old_symbol.start_line - 1 : old_symbol.end_line],
        after[new_symbol.start_line - 1 : new_symbol.end_line],
    )


def _commented_lines(ctx: RuleContext) -> list[str]:
    """The lines the comment is attached to, in the code before the change."""
    thread = ctx.case.thread
    anchor = ctx.case.anchor_line or 0
    span = 0
    if thread.original_start_line and thread.original_line:
        span = max(0, thread.original_line - thread.original_start_line)
    elif thread.start_line and thread.line:
        span = max(0, thread.line - thread.start_line)
    lines = (ctx.case.before_code or "").split("\n")
    return lines[max(0, anchor - 1 - span) : anchor]


def _normalized(lines: list[str]) -> list[str]:
    """Non-blank lines without any whitespace; a formatter's line split joined back."""
    return [re.sub(r"\s+", "", line) for line in lines if line.strip()]


def _exact(lines: list[str]) -> list[str]:
    return [line.rstrip() for line in lines if line.strip()]


def _count(block: list[str], lines: list[str]) -> int:
    """Occurrences of ``block`` in ``lines``, allowing each block line to span several lines."""
    if not block:
        return 0
    return sum(1 for i in range(len(lines)) if _match_at(block, lines, i) is not None)


def _match_at(block: list[str], lines: list[str], i: int) -> int | None:
    j = i
    for wanted in block:
        joined = ""
        target = _CLOSERS.sub(r"\1", wanted)
        while j < len(lines) and len(joined) < len(wanted) + 8:
            joined += lines[j]
            j += 1
            if _CLOSERS.sub(r"\1", joined) == target:
                break
        else:
            return None
        if _CLOSERS.sub(r"\1", joined) != target:
            return None
    return j


def _find(block: list[str], raw: list[str], exact: bool) -> int | None:
    """First line (1-based) where ``block`` starts in ``raw``."""
    kept = [(n, line) for n, line in enumerate(raw, start=1) if line.strip()]
    lines = [line.rstrip() if exact else re.sub(r"\s+", "", line) for _, line in kept]
    for i in range(len(lines)):
        if _match_at(block, lines, i) is not None:
            return kept[i][0]
    return None


def _outcome(
    requirement: Requirement,
    ctx: RuleContext,
    ok: bool,
    detail: str,
    line: int,
    version: str = "after",
) -> RuleOutcome:
    kind = "suggestion.applied" if ok else "suggestion.not_applied"
    return RuleOutcome(
        RuleStatus.SATISFIED if ok else RuleStatus.NOT_SATISFIED,
        detail,
        [located(requirement, kind, ok, detail, ctx.file, line, version=version)],
    )


# ---------------------------------------------------------------- removal


def _removal(requirement: Requirement, ctx: RuleContext, obj: str) -> RuleOutcome:
    names = [n for n in quoted_identifiers(obj) if n.split(".")[-1] in ctx.before_file.identifiers]
    if names:
        name = names[0].split(".")[-1]
        before = ctx.before.identifier_lines(name)
        after = ctx.after.identifier_lines(name)
        if not before:
            return inconclusive(requirement, f"`{name}` is not in the commented code.")
        if not after:
            return RuleOutcome(
                RuleStatus.SATISFIED,
                f"`{name}` was removed.",
                [
                    unlocated(
                        requirement,
                        "removal.done",
                        True,
                        f"`{name}` no longer appears in the target code.",
                        "absence has no location",
                    )
                ],
            )
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"`{name}` is still there.",
            [
                located(
                    requirement,
                    "removal.still_present",
                    False,
                    f"`{name}` is still used (line {after[0]}).",
                    ctx.file,
                    after[0],
                )
            ],
        )
    if not _THIS.fullmatch(obj.strip(" .!")):
        return inconclusive(requirement, "What to remove is not the commented code itself.")
    block = _normalized(_commented_lines(ctx))
    if not block:
        return inconclusive(requirement, "The commented lines are blank; nothing to compare.")
    count_before = _count(block, _normalized((ctx.case.before_code or "").split("\n")))
    count_after = _count(block, _normalized((ctx.case.after_code or "").split("\n")))
    anchor = ctx.case.anchor_line or 1
    if count_after < count_before:
        return RuleOutcome(
            RuleStatus.SATISFIED,
            "The commented code was removed.",
            [
                located(
                    requirement,
                    "removal.done",
                    True,
                    "The commented lines are gone.",
                    ctx.file,
                    anchor,
                    version="before",
                )
            ],
        )
    return RuleOutcome(
        RuleStatus.NOT_SATISFIED,
        "The commented code is still there.",
        [
            located(
                requirement,
                "removal.still_present",
                False,
                "The commented lines are unchanged.",
                ctx.file,
                anchor,
                version="before",
            )
        ],
    )


# ---------------------------------------------------------------- docstring


def _docstring(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    symbol_after = ctx.resolution.after or ctx.resolution.moved_to
    symbol_before = ctx.resolution.before
    if symbol_after is None or symbol_after.kind not in ("function", "method", "class"):
        return inconclusive(requirement, "The commented code is not a function or class.")
    new = _docstring_of(symbol_after.node)
    old = _docstring_of(symbol_before.node) if symbol_before is not None else None
    if new and new != old:
        return RuleOutcome(
            RuleStatus.SATISFIED,
            f"`{symbol_after.name}` has a docstring.",
            [
                located(
                    requirement,
                    "docstring.added",
                    True,
                    f"`{symbol_after.name}` now has a docstring.",
                    ctx.file,
                    symbol_after.start_line,
                )
            ],
            already_present=False,
        )
    detail = (
        f"`{symbol_after.name}` has no docstring."
        if not new
        else f"The docstring of `{symbol_after.name}` did not change."
    )
    return RuleOutcome(
        RuleStatus.NOT_SATISFIED,
        detail,
        [
            located(
                requirement, "docstring.missing", False, detail, ctx.file, symbol_after.start_line
            )
        ],
    )


def _docstring_of(definition: Node) -> str | None:
    body = definition.child_by_field_name("body")
    if body is None or not body.named_children:
        return None
    first = body.named_children[0]
    if first.type == "expression_statement" and first.named_children:
        value = first.named_children[0]
        if value.type == "string":
            return node_text(value)
    return None


# ---------------------------------------------------------------- use A instead of B


def _use_instead(requirement: Requirement, ctx: RuleContext, new: str, old: str) -> RuleOutcome:
    after, before = ctx.after.text(), ctx.before.text()

    def present(snippet: str, code: str) -> bool:
        return re.search(rf"(?<![\w.]){re.escape(snippet.rstrip('()'))}(?![\w])", code) is not None

    if not present(old, before) and not present(new, before):
        return inconclusive(requirement, f"Neither `{new}` nor `{old}` is in the commented code.")
    line = ctx.case.anchor_line or 1
    if present(new, after) and not present(old, after):
        return RuleOutcome(
            RuleStatus.SATISFIED,
            f"`{new}` is used instead of `{old}`.",
            [located(requirement, "use.done", True, f"`{new}` replaces `{old}`.", ctx.file, line)],
            already_present=present(new, before) and not present(old, before),
        )
    if present(old, after) and not present(new, after):
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"`{old}` is still used and `{new}` is not.",
            [
                located(
                    requirement, "use.not_done", False, f"`{old}` is still used.", ctx.file, line
                )
            ],
        )
    return inconclusive(requirement, f"Both or neither of `{new}` and `{old}` are used now.")
