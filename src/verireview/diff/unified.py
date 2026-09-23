"""Typed view of a unified diff, parsed with ``unidiff`` (plan §11: files, hunks, lines, ranges)."""

from dataclasses import dataclass

from unidiff.errors import UnidiffParseError
from unidiff.patch import PatchSet

DEV_NULL = "/dev/null"


class DiffParseError(ValueError):
    pass


@dataclass(frozen=True)
class DiffLine:
    number: int  # 1-based line number on its side (before for removed, after for added)
    text: str


@dataclass(frozen=True)
class DiffHunk:
    before_start: int
    before_length: int
    after_start: int
    after_length: int
    removed: tuple[DiffLine, ...]
    added: tuple[DiffLine, ...]


@dataclass(frozen=True)
class FileDiff:
    before_path: str | None  # None when the file was added
    after_path: str | None  # None when the file was deleted
    hunks: tuple[DiffHunk, ...]

    @property
    def removed_lines(self) -> frozenset[int]:
        return frozenset(line.number for h in self.hunks for line in h.removed)

    @property
    def added_lines(self) -> frozenset[int]:
        return frozenset(line.number for h in self.hunks for line in h.added)


def parse_unified_diff(text: str) -> list[FileDiff]:
    if not text.strip():
        return []
    try:
        patch = PatchSet(text)
    except UnidiffParseError as exc:
        raise DiffParseError(str(exc)) from exc
    return [
        FileDiff(
            before_path=_path(f.source_file),
            after_path=_path(f.target_file),
            hunks=tuple(
                DiffHunk(
                    before_start=h.source_start,
                    before_length=h.source_length,
                    after_start=h.target_start,
                    after_length=h.target_length,
                    removed=tuple(
                        DiffLine(ln.source_line_no, _strip_eol(ln.value))
                        for ln in h
                        if ln.is_removed and ln.source_line_no is not None
                    ),
                    added=tuple(
                        DiffLine(ln.target_line_no, _strip_eol(ln.value))
                        for ln in h
                        if ln.is_added and ln.target_line_no is not None
                    ),
                )
                for h in f
            ),
        )
        for f in patch
    ]


def _path(raw: str) -> str | None:
    if raw == DEV_NULL:
        return None
    return raw[2:] if raw.startswith(("a/", "b/")) else raw


def _strip_eol(value: str) -> str:
    return value.removesuffix("\n")
