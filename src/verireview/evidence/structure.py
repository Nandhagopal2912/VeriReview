"""Structural evidence (Phase 3): which function is targeted, did its *code* change, and how?

Replaces the Phase 2 line radius with the enclosing symbol, and ignores comments, docstrings
and formatting when deciding whether code changed. Individual added/removed facts (conditions,
calls, raises, handlers, returns) are reported as neutral evidence: judging whether they
satisfy the request is the job of the Phase 5 rules.
"""

from tree_sitter import Node

from verireview.contracts import (
    CodeLocation,
    Evidence,
    EvidenceSource,
    ReviewCase,
    ReviewRequirement,
)
from verireview.syntax import (
    CodeFacts,
    Fact,
    ResolutionMethod,
    Symbol,
    TargetResolution,
    diff_facts,
    extract_facts,
    find_symbol,
    index_symbols,
    parse,
    resolve_target,
    structural_tokens,
)

MAX_FACT_EVIDENCE = 12
_MAX_FACT_TEXT = 100
_FACT_LABEL = {
    "call": "call",
    "condition": "condition",
    "raise": "raise",
    "handler": "exception handler",
    "return": "return",
}


def structural_evidence(case: ReviewCase, requirement: ReviewRequirement) -> list[Evidence]:
    if case.before_code is None or case.after_code is None or case.anchor_line is None:
        return [
            _evidence(
                "code_unavailable",
                None,
                "Before/after code or the commented line is unavailable.",
                reason="missing before_code, after_code or anchor_line",
            )
        ]

    before, after = case.before_code, case.after_code
    resolution = resolve_target(before, after, case.anchor_line)
    evidence: list[Evidence] = []

    if resolution.before_has_errors or resolution.after_has_errors:
        which = [
            n
            for n, bad in (
                ("before", resolution.before_has_errors),
                ("after", resolution.after_has_errors),
            )
            if bad
        ]
        evidence.append(
            _evidence(
                "parse_error",
                None,
                f"The parser reported syntax errors ({', '.join(which)}); structure may be "
                "incomplete.",
                reason="syntax errors have no single location",
            )
        )

    evidence += _target_evidence(case, resolution)
    before_root, after_roots = _scopes(before, after, resolution)
    evidence.append(_target_changed(case, resolution, before_root, after_roots))
    evidence += _fact_evidence(case, before_root, after_roots)
    evidence += _other_symbols(case, resolution, before, after)
    evidence.append(_file_changed_structurally(case, before, after))
    return evidence


def _target_evidence(case: ReviewCase, resolution: TargetResolution) -> list[Evidence]:
    anchor = case.anchor_line
    target = resolution.before
    if target is None:
        return [
            _evidence(
                "target_symbol",
                None,
                f"Commented line {anchor} is at module level (not inside a function or class).",
                reason="module-level target has no enclosing symbol",
            )
        ]
    items = [
        _evidence(
            "target_symbol",
            None,
            f"Commented line {anchor} is in {target.kind} `{target.qualified_name}`.",
            location=_loc(case, target, "before"),
        )
    ]
    after = resolution.after
    if after is None:
        items.append(
            _evidence(
                "target_after",
                None,
                f"`{target.qualified_name}` no longer exists after the changes.",
                reason="target symbol not found after the changes",
            )
        )
    elif resolution.method == ResolutionMethod.RENAMED:
        items.append(
            _evidence(
                "target_after",
                None,
                f"`{target.qualified_name}` was renamed to `{after.qualified_name}` "
                f"(structural similarity {resolution.similarity:.2f}).",
                location=_loc(case, after, "after"),
            )
        )
    else:
        items.append(
            _evidence(
                "target_after",
                None,
                f"`{target.qualified_name}` still exists after the changes.",
                location=_loc(case, after, "after"),
            )
        )
    if resolution.moved_to is not None:
        moved = resolution.moved_to
        items.append(
            _evidence(
                "target_moved",
                None,
                f"The commented line now lives in {moved.kind} `{moved.qualified_name}` "
                f"(line {resolution.anchor_after_line}).",
                location=_loc(case, moved, "after"),
            )
        )
    return items


def _scopes(before: str, after: str, resolution: TargetResolution) -> tuple[Node, list[Node]]:
    """Syntax nodes to compare: the target (plus where its code moved), or the whole module."""
    if resolution.before is None:
        return parse(before).root_node, [parse(after).root_node]
    after_nodes = [s.node for s in (resolution.after, resolution.moved_to) if s is not None]
    return resolution.before.node, after_nodes


def _target_changed(
    case: ReviewCase, resolution: TargetResolution, before_root: Node, after_roots: list[Node]
) -> Evidence:
    name = f"`{resolution.before.qualified_name}`" if resolution.before else "the module"
    before_tokens = structural_tokens(before_root)
    after_tokens = tuple(t for root in after_roots for t in structural_tokens(root))
    location = (
        _loc(case, resolution.after, "after")
        if resolution.after is not None
        else _loc(case, resolution.before, "before")
        if resolution.before is not None
        else None
    )
    reason = None if location else "module-level comparison"

    if resolution.before is not None and resolution.after is None:
        return _evidence(
            "target_changed_structurally",
            True,
            f"{name} was removed or rewritten beyond recognition.",
            location=location,
            reason=reason,
        )
    if before_tokens != after_tokens or resolution.moved_to is not None:
        return _evidence(
            "target_changed_structurally",
            True,
            f"{name} changed structurally (code, not only comments or formatting).",
            location=location,
            reason=reason,
        )
    texts_differ = [_text(before_root)] != [_text(r) for r in after_roots]
    detail = (
        f"Only comments, docstrings or formatting changed in {name}."
        if texts_differ
        else f"{name} is unchanged."
    )
    return _evidence("target_changed_structurally", False, detail, location=location, reason=reason)


def _fact_evidence(case: ReviewCase, before_root: Node, after_roots: list[Node]) -> list[Evidence]:
    after_facts = CodeFacts()
    for root in after_roots:
        after_facts = after_facts.merged(extract_facts(root))
    diff = diff_facts(extract_facts(before_root), after_facts)
    items = [_fact("added", f, case, "after") for f in diff.added]
    items += [_fact("removed", f, case, "before") for f in diff.removed]
    if len(items) > MAX_FACT_EVIDENCE:
        hidden = len(items) - MAX_FACT_EVIDENCE
        items = items[:MAX_FACT_EVIDENCE] + [
            _evidence(
                "more_structural_changes",
                None,
                f"…and {hidden} more structural change(s) not listed.",
                reason="list truncated",
            )
        ]
    return items


def _fact(change: str, fact: Fact, case: ReviewCase, version: str) -> Evidence:
    text = fact.text if len(fact.text) <= _MAX_FACT_TEXT else fact.text[:_MAX_FACT_TEXT] + "…"
    path = case.file_path if version == "after" else case.thread.path
    return _evidence(
        f"{change}_{fact.kind}",
        None,
        f"{change.capitalize()} {_FACT_LABEL[fact.kind]} `{text}`.",
        location=CodeLocation(file=path, line_start=fact.line, line_end=fact.line, version=version),
    )


def _other_symbols(
    case: ReviewCase, resolution: TargetResolution, before: str, after: str
) -> list[Evidence]:
    """Changes outside the target: unrelated edits, or upstream drift (Phase 1 live check L3)."""
    before_symbols = index_symbols(parse(before))
    after_symbols = index_symbols(parse(after))
    related = {
        s.qualified_name
        for s in (resolution.before, resolution.after, resolution.moved_to)
        if s is not None
    }
    changed: list[str] = []
    first: Symbol | None = None
    for symbol in after_symbols:
        if symbol.qualified_name in related or _inside_related(symbol, related):
            continue
        old = find_symbol(before_symbols, symbol.qualified_name)
        if old is None or structural_tokens(old.node) != structural_tokens(symbol.node):
            changed.append(symbol.qualified_name)
            first = first or symbol
    removed = [
        s.qualified_name
        for s in before_symbols
        if s.qualified_name not in related
        and not _inside_related(s, related)
        and find_symbol(after_symbols, s.qualified_name) is None
    ]
    names = changed + [f"{n} (removed)" for n in removed]
    if not names:
        return []
    return [
        _evidence(
            "other_symbols_changed",
            None,
            "Code outside the target also changed: " + ", ".join(f"`{n}`" for n in names) + ".",
            location=_loc(case, first, "after") if first else None,
            reason=None if first else "only removed symbols",
        )
    ]


def _inside_related(symbol: Symbol, related: set[str]) -> bool:
    """Enclosing classes of the target, and symbols nested in it, are part of the target."""
    name = symbol.qualified_name
    return any(r.startswith(name + ".") or name.startswith(r + ".") for r in related)


def _file_changed_structurally(case: ReviewCase, before: str, after: str) -> Evidence:
    changed = structural_tokens(parse(before).root_node) != structural_tokens(
        parse(after).root_node
    )
    if not changed:
        return _evidence(
            "file_changed_structurally",
            False,
            "The file's code did not change (at most comments, docstrings or formatting).",
            reason="no structural change in the file",
        )
    return _evidence(
        "file_changed_structurally",
        True,
        "The file's code changed.",
        location=CodeLocation(
            file=case.file_path,
            line_start=1,
            line_end=max(1, after.count("\n")),
            version="after",
        ),
    )


def _loc(case: ReviewCase, symbol: Symbol, version: str) -> CodeLocation:
    path = case.file_path if version == "after" else case.thread.path
    return CodeLocation(
        file=path, line_start=symbol.start_line, line_end=symbol.end_line, version=version
    )


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", errors="replace")


def _evidence(
    kind: str,
    passed: bool | None,
    detail: str,
    location: CodeLocation | None = None,
    reason: str | None = None,
) -> Evidence:
    return Evidence(
        id="?",
        requirement_id=None,
        source=EvidenceSource.AST,
        kind=kind,
        passed=passed,
        detail=detail,
        location=location,
        no_location_reason=reason if location is None else None,
    )
