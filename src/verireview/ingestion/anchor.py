"""Locate the commented line in ``before_code`` from the comment's ``diff_hunk``.

GitHub's ``original_line`` is not always consistent with the file at ``original_commit_id``
(live check: pallets/click#2811 was off by 3 lines while the fetched file was byte-identical to
the commit). The ``diff_hunk`` text is reliable: GitHub cuts it off at the commented line, so
its last new-side line *is* the reviewed line.
"""

# Match at most this many trailing new-side lines; long hunks with local edits still anchor.
_MAX_CONTEXT = 6


def locate_comment_line(
    before_code: str, diff_hunk: str, side: str | None, original_line: int | None
) -> int | None:
    """1-based line in ``before_code`` the comment points at, or None if it cannot be found.

    Only RIGHT-side comments can be anchored: LEFT-side comments point at deleted base lines,
    which by definition are not in the reviewed commit's file.
    """
    if side == "LEFT":
        return None
    body = [line for line in diff_hunk.splitlines() if not line.startswith(("@@", "\\"))]
    if not body or body[-1].startswith("-"):
        return None
    new_side = [line[1:] for line in body if line[:1] in (" ", "+")]
    lines = before_code.split("\n")

    # Prefer the longest trailing context that matches, so short generic lines ("    )") still
    # anchor correctly when surrounded by distinctive ones.
    for size in range(min(len(new_side), _MAX_CONTEXT), 0, -1):
        needle = new_side[-size:]
        ends = [
            start + size
            for start in range(len(lines) - size + 1)
            if lines[start : start + size] == needle
        ]
        if ends:
            if original_line is None:
                return ends[0] if len(ends) == 1 else None
            return min(ends, key=lambda end: abs(end - original_line))
    return None
