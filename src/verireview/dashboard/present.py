"""Turn a stored verification into what the detail page shows (plain data; the templates escape).

Code excerpts, diff lines and evidence rows are built here so the templates stay free of logic.
Everything taken from the repository stays a plain string: Jinja2 autoescaping renders it as
text, and no template marks anything ``|safe``.
"""

from dataclasses import dataclass
from typing import Any

from verireview.contracts import Evidence, ReviewCase, VerificationResult

EXCERPT_RADIUS = 8
MAX_DIFF_LINES = 400


@dataclass(frozen=True)
class CodeLine:
    number: int
    text: str
    marked: bool


@dataclass(frozen=True)
class DiffLine:
    text: str
    kind: str  # "add" | "del" | "hunk" | "meta" | "ctx"


@dataclass(frozen=True)
class EvidenceRow:
    id: str
    requirement: str
    kind: str
    passed: bool | None
    detail: str
    where: str


@dataclass(frozen=True)
class Detail:
    result: VerificationResult
    evidence: list[EvidenceRow]
    case: ReviewCase | None
    before: list[CodeLine]
    after: list[CodeLine]
    diff: list[DiffLine]
    diff_truncated: bool


def detail(result_json: dict[str, Any], case_json: dict[str, Any] | None) -> Detail:
    result = VerificationResult.model_validate(result_json)
    case = ReviewCase.model_validate(case_json) if case_json else None
    before: list[CodeLine] = []
    after: list[CodeLine] = []
    diff: list[DiffLine] = []
    truncated = False
    if case is not None:
        if case.before_code is not None and case.anchor_line is not None:
            before = excerpt(case.before_code, case.anchor_line, {case.anchor_line})
        if case.after_code is not None:
            marked = _after_lines(result.evidence, case)
            centre = min(marked) if marked else case.anchor_line or 1
            after = excerpt(case.after_code, centre, marked)
        diff, truncated = diff_lines(case.unified_diff)
    return Detail(
        result=result,
        evidence=[_row(e) for e in result.evidence],
        case=case,
        before=before,
        after=after,
        diff=diff,
        diff_truncated=truncated,
    )


def excerpt(code: str, centre: int, marked: set[int]) -> list[CodeLine]:
    lines = code.split("\n")
    low = max(1, centre - EXCERPT_RADIUS)
    high = min(len(lines), centre + EXCERPT_RADIUS)
    return [CodeLine(n, lines[n - 1], n in marked) for n in range(low, high + 1)]


def diff_lines(diff: str) -> tuple[list[DiffLine], bool]:
    lines = diff.split("\n") if diff else []
    out = [DiffLine(line, _diff_kind(line)) for line in lines[:MAX_DIFF_LINES]]
    return out, len(lines) > MAX_DIFF_LINES


def _diff_kind(line: str) -> str:
    if line.startswith(("+++", "---")):
        return "meta"
    if line.startswith("@@"):
        return "hunk"
    if line.startswith("+"):
        return "add"
    if line.startswith("-"):
        return "del"
    return "ctx"


def _after_lines(evidence: list[Evidence], case: ReviewCase) -> set[int]:
    """Lines of the commented file (after) that located evidence points at."""
    lines: set[int] = set()
    for e in evidence:
        loc = e.location
        if loc is None or loc.file != case.file_path or loc.version == "before":
            continue
        if loc.version not in ("after", case.head_sha[: len(loc.version)]):
            continue
        lines.update(range(loc.line_start, min(loc.line_end, loc.line_start + 20) + 1))
    return lines


def _row(e: Evidence) -> EvidenceRow:
    where = (
        f"{e.location.file}:{e.location.line_start}"
        + (f"-{e.location.line_end}" if e.location.line_end != e.location.line_start else "")
        + f" @ {e.location.version[:7]}"
        if e.location
        else e.no_location_reason or ""
    )
    return EvidenceRow(
        id=e.id,
        requirement=e.requirement_id or "all",
        kind=e.kind,
        passed=e.passed,
        detail=e.detail,
        where=where,
    )
