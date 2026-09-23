"""Plain-text explanation built only from recorded evidence (plan §16): nothing is invented.

Layout (plan §16):

    Review request:  the reviewer's words
    Requirements:    ✓ satisfied / ✗ missing / ? undecided, one line per requirement
    Evidence:        every evidence item, with file:line @ commit
    Result, Confidence, Notes
"""

from verireview.contracts import (
    CodeLocation,
    Confidence,
    Evidence,
    RequirementStatus,
    ReviewCase,
    ReviewRequirement,
    Verdict,
)

_MARK = {True: "✓", False: "✗", None: "•"}
_STATUS_MARK = {
    Verdict.SATISFIED: "✓",
    Verdict.NOT_SATISFIED: "✗",
    Verdict.PARTIALLY_SATISFIED: "~",
    Verdict.UNCERTAIN: "?",
}
_MAX_REQUEST_CHARS = 300


def render_explanation(
    case: ReviewCase,
    requirement: ReviewRequirement,
    evidence: list[Evidence],
    verdict: Verdict,
    confidence: Confidence,
    notes: list[str],
    statuses: list[RequirementStatus] | None = None,
) -> str:
    request = case.thread.root.body.strip()
    if len(request) > _MAX_REQUEST_CHARS:
        request = request[:_MAX_REQUEST_CHARS].rstrip() + "…"
    lines = [f'Review request:\n"{request}"', "", "Requirements:"]
    by_id = {s.requirement_id: s.status for s in statuses or []}
    for r in requirement.requirements:
        mark = _STATUS_MARK.get(by_id[r.id], "•") if r.id in by_id else "•"
        lines.append(f"{mark} {r.id} ({r.category.value}): {r.description}")
    lines += ["", "Evidence:"]
    lines += [f"{_MARK[e.passed]} [{e.id}] {e.detail}{_where(e.location, case)}" for e in evidence]
    lines += ["", f"Result:\n{verdict.value}", "", f"Confidence:\n{confidence.value}"]
    if notes:
        lines += ["", "Notes:"] + [f"- {n}" for n in notes]
    return "\n".join(lines)


def _where(location: CodeLocation | None, case: ReviewCase) -> str:
    if location is None:
        return ""
    span = (
        str(location.line_start)
        if location.line_start == location.line_end
        else f"{location.line_start}-{location.line_end}"
    )
    return f" ({location.file}:{span} @ {_commit(location.version, case)})"


def _commit(version: str, case: ReviewCase) -> str:
    """'before'/'after' → the window's start/end commit; a SHA stays a (short) SHA."""
    sha = {
        "before": case.window.start_commit_sha,
        "after": case.window.end_commit_sha,
    }.get(version, version)
    return f"{sha[:7]} ({version})" if version in ("before", "after") else sha[:7]
