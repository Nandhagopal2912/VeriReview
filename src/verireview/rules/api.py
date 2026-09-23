"""API-behaviour rule (plan §12): "Return HTTP 400 for invalid input."

1. Which status the request wants: numbers / names ("201 Created", "Not Found") that are not
   marked as the current or wrong behaviour ("not 200", "instead of 400", "right now this is a
   500").
2. Is that status produced (a return or abort-like call) in the target code?
3. Is it on the right branch: under a condition that tests the values the request talks about
   ("when `username` is missing" → a branch on `username`)?
4. Headers: "include a `Location` header" → the header name appears in the new code.
If what is produced is a different status on that branch (404 asked, 400 returned), that is
reported explicitly. ADR-001: the same status on the same branch before the comment → already
present.
"""

import re

from verireview.contracts import Evidence, Requirement
from verireview.rules.analysis import HTTP_STATUS, StatusSite
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
    located,
    quoted_identifiers,
    requested_identifiers,
    unlocated,
)

_NAMED = {
    "created": 201,
    "no content": 204,
    "bad request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not found": 404,
    "conflict": 409,
    "unprocessable": 422,
}
_CODE = re.compile(r"\b(\d{3})\b")
_NOT_WANTED_BEFORE = re.compile(
    r"(not|instead of|rather than|than|right now|currently|at the moment|this is an?)\s*$", re.I
)


def api_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    text = f"{requirement.description} {requirement.condition or ''}"
    wanted = _wanted_codes(text)
    if not wanted:
        if re.search(r"\bheaders?\b", text, re.I):
            return _header(requirement, ctx)
        return inconclusive(requirement, "The request names no HTTP status to check.")

    names = set(requested_identifiers(requirement, ctx))
    conditional = bool(requirement.condition) or bool(names)
    sites = ctx.after.responses()
    evidence: list[Evidence] = []
    for code in wanted:
        hit = next((s for s in sites if s.code == code and _on_branch(s, names, conditional)), None)
        if hit is None:
            evidence += _explain_missing(requirement, ctx, code, sites, names)
            return RuleOutcome(
                RuleStatus.NOT_SATISFIED, f"HTTP {code} is not returned where requested.", evidence
            )
        where = f" when `{_branch_text(hit)}`" if hit.branch else ""
        evidence.append(
            located(
                requirement,
                "api.status_returned",
                True,
                f"`{hit.text}` returns HTTP {code}{where}.",
                ctx.file,
                hit.line,
            )
        )

    before_sites = {(s.code, _branch_text(s)) for s in ctx.before.responses()}
    already = all(
        (s.code, _branch_text(s)) in before_sites
        for s in sites
        if s.code in wanted and _on_branch(s, names, conditional)
    )
    if already:
        evidence.append(
            unlocated(
                requirement,
                "already_present",
                True,
                "The requested response already existed before the comment (ADR-001).",
                "state predates the comment",
            )
        )
    return RuleOutcome(
        RuleStatus.SATISFIED, "The requested status is returned.", evidence, already_present=already
    )


def _wanted_codes(text: str) -> list[int]:
    codes: list[int] = []
    for match in _CODE.finditer(text):
        code = int(match.group(1))
        if code in HTTP_STATUS and not _NOT_WANTED_BEFORE.search(text[: match.start()]):
            codes.append(code)
    lowered = text.lower()
    for name, code in _NAMED.items():
        if (
            name in lowered
            and code not in codes
            and not _NOT_WANTED_BEFORE.search(lowered[: lowered.index(name)])
        ):
            codes.append(code)
    return list(dict.fromkeys(codes))


def _on_branch(site: StatusSite, names: set[str], conditional: bool) -> bool:
    """Returned under a (non-negated) condition on the requested values, if any are named."""
    if not conditional:
        return True
    positive = [b for b in site.branch if not b.negated]
    if not positive:
        return False
    return not names or any(b.condition.identifiers & names for b in positive)


def _branch_text(site: StatusSite) -> str:
    return " and ".join(b.condition.text for b in site.branch if not b.negated)


def _explain_missing(
    requirement: Requirement,
    ctx: RuleContext,
    code: int,
    sites: list[StatusSite],
    names: set[str],
) -> list[Evidence]:
    relevant = [s for s in sites if any(b.condition.identifiers & names for b in s.branch)]
    if relevant:
        s = relevant[0]
        return [
            located(
                requirement,
                "api.wrong_status",
                False,
                f"When `{_branch_text(s)}`, the code returns HTTP {s.code} "
                f"(`{s.text}`), not {code}.",
                ctx.file,
                s.line,
            )
        ]
    return [
        unlocated(
            requirement,
            "api.status_missing",
            False,
            f"No response with HTTP {code} on the requested branch.",
            "absence has no location",
        )
    ]


def _header(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    headers = quoted_identifiers(requirement.description)
    if not headers:
        return inconclusive(requirement, "The request names no header.")
    name = headers[0]
    before, after = ctx.before.text(), ctx.after.text()
    for quote in ('"', "'"):
        literal = f"{quote}{name}{quote}"
        if literal in after:
            line = (
                ctx.after_file.text()
                .split("\n")
                .index(next(ln for ln in ctx.after_file.text().split("\n") if literal in ln))
                + 1
            )
            return RuleOutcome(
                RuleStatus.SATISFIED,
                f"The `{name}` header is set.",
                [
                    located(
                        requirement,
                        "api.header_set",
                        True,
                        f"The response sets the `{name}` header.",
                        ctx.file,
                        line,
                    )
                ],
                already_present=literal in before,
            )
    return RuleOutcome(
        RuleStatus.NOT_SATISFIED,
        f"The `{name}` header is not set.",
        [
            unlocated(
                requirement,
                "api.header_missing",
                False,
                f"No `{name}` header in the response.",
                "absence has no location",
            )
        ],
    )
