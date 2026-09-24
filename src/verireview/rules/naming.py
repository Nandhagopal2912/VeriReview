"""Naming rule (plan §12): rename `old` to `new`.

Checks, in the relevant scope (the whole file if `old` names a function/class, else the target
function):
1. `old` no longer appears as an identifier (comments and strings don't count, so a comment
   that merely *mentions* the new name is not a rename).
2. If a new name was demanded ("rename `a` to `b`", "`a` -> `b`"), `b` is used. If it was only
   an example ("a name like `b`", "e.g. `b`"), any new identifier replacing `a` is fine.
ADR-001: `old` absent and `new` already present before the comment → satisfied, already present.
"""

import re

from verireview.contracts import Requirement
from verireview.requirements import lexicon as lx
from verireview.rules.analysis import Scope
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
    located,
    quoted_identifiers,
    unlocated,
)

_STRICT_NEW = re.compile(r"\b(?:to|->|→|=>)\s+`([A-Za-z_]\w*)`")
_SOFT_NEW = re.compile(r"\b(?:like|e\.g\.,?|such as|maybe|perhaps)\s+`([A-Za-z_]\w*)`", re.I)


def naming_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    old, new, strict = _rename_request(requirement, ctx)
    if old is None:
        return inconclusive(requirement, "The request does not say which name to change.")

    before, after = _scopes(old, ctx)
    old_before = before.identifier_lines(old)
    if not old_before:
        if new and after.identifier_lines(new) and before.identifier_lines(new):
            return RuleOutcome(
                RuleStatus.SATISFIED,
                f"`{new}` was already used before the comment.",
                [
                    unlocated(
                        requirement,
                        "naming.already_named",
                        True,
                        f"`{old}` does not occur and `{new}` was already used.",
                        "requested state predates the comment",
                    )
                ],
                already_present=True,
            )
        return inconclusive(requirement, f"`{old}` does not appear in the reviewed code.")

    evidence = []
    old_after = after.identifier_lines(old)
    # A compatibility alias (`get_user = fetch_user`) keeps the old name only as a pointer to the
    # new one: the rename is done (Phase 10.1, adversarial a-naming-06).
    aliases = _alias_lines(old, new, ctx)
    if aliases:
        old_after = [line for line in old_after if line not in aliases]
        evidence.append(
            located(
                requirement,
                "naming.compatibility_alias",
                None,
                f"`{old}` remains only as an alias of `{new}` (line {aliases[0]}).",
                ctx.file,
                aliases[0],
            )
        )
    if old_after:
        evidence.append(
            located(
                requirement,
                "naming.old_name_remains",
                False,
                f"`{old}` is still used as an identifier (line(s) "
                f"{', '.join(map(str, old_after))}).",
                ctx.file,
                old_after[0],
            )
        )
    else:
        evidence.append(
            unlocated(
                requirement,
                "naming.old_name_removed",
                True,
                f"`{old}` no longer appears as an identifier.",
                "absence has no location",
            )
        )

    introduced = sorted(after.identifiers - before.identifiers)
    new_lines = after.identifier_lines(new) if new else []
    if new_lines:
        renamed_ok = True
        evidence.append(
            located(
                requirement,
                "naming.new_name_used",
                True,
                f"`{new}` is used (line {new_lines[0]}).",
                ctx.file,
                new_lines[0],
            )
        )
    elif new and strict:
        renamed_ok = False
        evidence.append(
            unlocated(
                requirement,
                "naming.new_name_missing",
                False,
                f"The requested name `{new}` is not used.",
                "absence has no location",
            )
        )
    else:
        # No name demanded (or only an example): any new identifier replacing `old` counts.
        renamed_ok = bool(introduced)
        if introduced:
            evidence.append(
                unlocated(
                    requirement,
                    "naming.new_identifiers",
                    None,
                    "New identifiers: " + ", ".join(f"`{n}`" for n in introduced) + ".",
                    "summary of added names",
                )
            )

    if not old_after and renamed_ok:
        return RuleOutcome(RuleStatus.SATISFIED, f"`{old}` was renamed.", evidence)
    reason = f"`{old}` is still used" if old_after else f"`{old}` was not replaced by `{new}`"
    return RuleOutcome(RuleStatus.NOT_SATISFIED, reason + ".", evidence)


def _rename_request(
    requirement: Requirement, ctx: RuleContext
) -> tuple[str | None, str | None, bool]:
    """(old name, new name, whether the new name is mandatory)."""
    known = ctx.before_file.identifiers
    # Pairs in this requirement's own text first; a pair elsewhere in the comment only if it is
    # about this requirement's target (another requirement's rename must not leak in).
    for a, b in lx.RENAME_ARROW.findall(requirement.description) or lx.RENAME_PAIR.findall(
        requirement.description
    ):
        return a, b, True
    for a, b in lx.RENAME_ARROW.findall(ctx.comment) or lx.RENAME_PAIR.findall(ctx.comment):
        if requirement.target is not None and a == requirement.target:
            return a, b, True

    names = quoted_identifiers(requirement.description) + quoted_identifiers(ctx.comment)
    old = requirement.target if requirement.target in known else None
    old = old or next((n for n in names if n in known), None)

    new: str | None = None
    strict = False
    if requirement.suggested_code:
        suggested = [t for t in re.findall(r"[A-Za-z_]\w*", requirement.suggested_code)]
        new = next((t for t in suggested if t not in known), None)
        strict = new is not None
    for text in (requirement.description, ctx.comment):
        if new:
            break
        if match := _STRICT_NEW.search(text):
            new, strict = match.group(1), True
        elif match := _SOFT_NEW.search(text):
            new, strict = match.group(1), False
    if new == old:
        new = None
    return old, new, strict


def _alias_lines(old: str, new: str | None, ctx: RuleContext) -> list[int]:
    """Lines `old = new` (or `old = deprecated(new)`) in the file after the change."""
    if not new:
        return []
    pattern = re.compile(rf"^\s*{re.escape(old)}\s*=\s*.*\b{re.escape(new)}\b")
    lines = (ctx.case.after_code or "").split("\n")
    return [i for i, text in enumerate(lines, start=1) if pattern.match(text)]


def _scopes(old: str, ctx: RuleContext) -> tuple[Scope, Scope]:
    """A function/class name is referenced file-wide; anything else lives in the target."""
    if old in ctx.before_file.defined_names():
        return ctx.before_file, ctx.after_file
    return ctx.before, ctx.after
