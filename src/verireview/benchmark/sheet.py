"""The annotation page: one self-contained, offline HTML file per batch (Phase 9).

Modes:
- ``annotate``: blind labelling (docs/annotation_guide.md). Exports an ``AnnotationFile``.
- ``calibration``: the same, on dev fixtures, with a "reveal reference" button per case.
- ``adjudicate``: both annotators' labels side by side for the disputed cases. Exports an
  ``AdjudicationFile``.

Case content comes from third-party repositories and is untrusted: it is embedded as JSON with
``<``, ``>`` and ``&`` escaped, and the page only ever inserts it as text (``textContent``), never
as HTML. The page loads nothing from the network. Work in progress is kept in the browser's
localStorage; the exported JSON file is what counts.
"""

import json
from importlib.resources import files
from typing import Any, Literal

from pydantic import BaseModel

from verireview.contracts import ReviewCase
from verireview.ingestion import make_unified_diff

SHEET_VERSION = "phase9-sheet-1"
EXCERPT_RADIUS = 25
Mode = Literal["annotate", "calibration", "adjudicate"]


class SheetComment(BaseModel):
    author: str
    body: str


class SheetCase(BaseModel):
    case_id: str
    repository: str
    file_path: str
    anchor_line: int | None
    selection_start: int | None = None  # first commented line of a multi-line comment
    thread: list[SheetComment]
    before_excerpt: list[tuple[int, str]]
    diff: str
    test_diffs: list[tuple[str, str]]
    before_full: str
    after_full: str
    commits: int
    flags: list[str]
    reference: dict[str, Any] | None = None  # calibration only


def sheet_case(
    case_id: str, case: ReviewCase, reference: dict[str, Any] | None = None
) -> SheetCase:
    before = case.before_code or ""
    lines = before.split("\n")
    anchor = case.anchor_line or case.thread.original_line or 1
    selection = _selection_start(case, anchor)
    first = selection if selection is not None else anchor
    start, end = max(1, first - EXCERPT_RADIUS), min(len(lines), anchor + EXCERPT_RADIUS)
    tests = [
        (path, make_unified_diff(case.test_files_before.get(path, ""), after, path, path))
        for path, after in sorted(case.test_files.items())
    ]
    return SheetCase(
        case_id=case_id,
        repository=case.repository,
        file_path=case.file_path,
        anchor_line=case.anchor_line,
        selection_start=selection,
        thread=[SheetComment(author=c.author or "?", body=c.body) for c in case.thread.comments],
        before_excerpt=[(n, lines[n - 1]) for n in range(start, end + 1)],
        diff=case.unified_diff,
        test_diffs=tests,
        before_full=before,
        after_full=case.after_code or "",
        commits=len(case.window.subsequent_commits),
        flags=[f.value for f in case.window.flags],
        reference=reference,
    )


def _selection_start(case: ReviewCase, anchor: int) -> int | None:
    """Start of a multi-line comment's selection, shifted like the anchor line. A multi-line
    comment matters: an empty ``suggestion`` block deletes the whole selection."""
    thread = case.thread
    if thread.original_start_line is None or thread.original_line is None:
        return None
    span = thread.original_line - thread.original_start_line
    return max(1, anchor - span) if span > 0 else None


def render_sheet(
    cases: list[SheetCase],
    batch: str,
    mode: Mode = "annotate",
    pair: dict[str, Any] | None = None,
) -> str:
    """``pair`` (adjudicate mode): {"a": AnnotationFile json, "b": ..., "disputed": [ids]}."""
    payload = {
        "version": SHEET_VERSION,
        "batch": batch,
        "mode": mode,
        "cases": [c.model_dump(mode="json") for c in cases],
        "pair": pair,
    }
    data = (
        json.dumps(payload, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return _template().replace("__DATA__", data).replace("__TITLE__", _title(mode, batch))


def _title(mode: Mode, batch: str) -> str:
    safe = "".join(ch for ch in batch if ch.isalnum() or ch in "-_. ")
    return {"annotate": "Annotate", "calibration": "Calibration", "adjudicate": "Adjudicate"}[
        mode
    ] + f" · {safe}"


def _template() -> str:
    return files("verireview.benchmark").joinpath("sheet_template.html").read_text(encoding="utf-8")
