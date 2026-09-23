"""Plain-text explanation built only from recorded evidence (plan §16): nothing is invented."""

from verireview.contracts import (
    CodeLocation,
    Confidence,
    Evidence,
    ReviewCase,
    ReviewRequirement,
    Verdict,
)

_MARK = {True: "✓", False: "✗", None: "•"}
_MAX_REQUEST_CHARS = 300


def render_explanation(
    case: ReviewCase,
    requirement: ReviewRequirement,
    evidence: list[Evidence],
    verdict: Verdict,
    confidence: Confidence,
    notes: list[str],
) -> str:
    request = case.thread.root.body.strip()
    if len(request) > _MAX_REQUEST_CHARS:
        request = request[:_MAX_REQUEST_CHARS].rstrip() + "…"
    lines = [f'Review request:\n"{request}"', "", "Evidence:"]
    lines += [f"{_MARK[e.passed]} [{e.id}] {e.detail}{_where(e.location)}" for e in evidence]
    if len(requirement.requirements) > 1:
        lines += ["", "Requirements:"]
        lines += [f"- {r.id}: {r.description}" for r in requirement.requirements]
    lines += ["", f"Result:\n{verdict.value}", "", f"Confidence:\n{confidence.value}"]
    if notes:
        lines += ["", "Notes:"] + [f"- {n}" for n in notes]
    return "\n".join(lines)


def _where(location: CodeLocation | None) -> str:
    if location is None:
        return ""
    span = (
        str(location.line_start)
        if location.line_start == location.line_end
        else f"{location.line_start}-{location.line_end}"
    )
    return f" ({location.file}:{span}, {location.version})"
