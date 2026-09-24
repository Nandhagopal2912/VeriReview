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

Phase 10.1: statuses may be names (`HTTPStatus.BAD_REQUEST`) or raised HTTP exceptions (also
custom ones an `@app.errorhandler` maps); an `except` clause is a branch; unreachable code does
not count; "when X is not found" needs a branch where X is absent (`if not user`, not
`if user`); a request without a condition ("creating a note should return 201") needs no branch.
Without a status: "include the id in the error message" checks the error responses, and
"return an empty list instead of None" checks the returned values.
"""

import re

from verireview.contracts import Evidence, Requirement
from verireview.requirements import lexicon as lx
from verireview.rules.analysis import HTTP_STATUS, StatusSite, error_handler_codes
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
    located,
    quoted_identifiers,
    related_identifiers,
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
    r"(not|instead of|rather than|than|right now|currently|at the moment|this is)(\s+an?)?\s*$",
    re.I,
)


def api_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    text = f"{requirement.description} {requirement.condition or ''}"
    wanted = _wanted_codes(text)
    if not wanted:
        if re.search(r"\bheaders?\b", text, re.I):
            return _header(requirement, ctx)
        if _MESSAGE.search(text):
            return _message(requirement, ctx)
        if lx.RETURN_VALUE.search(text):
            return _return_value(requirement, ctx)
        return inconclusive(requirement, "The request names no HTTP status to check.")

    requested = requested_identifiers(requirement, ctx)
    conditional = bool(requirement.condition) or (
        bool(requested) and _CONDITIONAL.search(text) is not None
    )
    absence = _ABSENCE.search(text) is not None
    # "when the item is missing" may be tested on `found = get_item(item_id)`: the request's
    # content words count as name tokens, then assignments carry them to derived variables.
    seeds = requested + _content_words(text)
    names = related_identifiers(seeds, ctx.after) & ctx.after.identifiers if seeds else set()
    sites = ctx.after.responses(error_handler_codes(ctx.after_file))
    # A condition was stated but none of its values can be found in the code: the branch cannot
    # be checked, so never accept "some branch returns the code" (Phase 5.1 adversarial test).
    if conditional and not names and any(s.code in wanted and s.branch for s in sites):
        return inconclusive(
            requirement,
            f"HTTP {'/'.join(map(str, wanted))} is returned conditionally, but the condition "
            "in the request cannot be matched to the code.",
        )
    evidence: list[Evidence] = []
    for code in wanted:
        hit = next(
            (s for s in sites if s.code == code and _on_branch(s, names, conditional, absence)),
            None,
        )
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

    before_sites = {
        (s.code, _branch_text(s))
        for s in ctx.before.responses(error_handler_codes(ctx.before_file))
    }
    already = all(
        (s.code, _branch_text(s)) in before_sites
        for s in sites
        if s.code in wanted and _on_branch(s, names, conditional, absence)
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


_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "not",
        "no",
        "when",
        "if",
        "is",
        "are",
        "was",
        "be",
        "been",
        "does",
        "doesn",
        "don",
        "exist",
        "exists",
        "missing",
        "return",
        "returns",
        "respond",
        "with",
        "for",
        "on",
        "in",
        "of",
        "to",
        "from",
        "this",
        "that",
        "it",
        "its",
        "http",
        "status",
        "code",
        "error",
        "errors",
        "message",
        "body",
        "request",
        "response",
        "should",
        "must",
        "invalid",
        "input",
        "found",
        "instead",
        "right",
        "now",
        "currently",
        "header",
        "headers",
        "raise",
    ]
)


def _content_words(text: str) -> list[str]:
    """Words that can name a value ("invoice", "user"); stop words and codes removed."""
    plain = re.sub(r"`[^`]*`", " ", text)
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", plain)]
    return [w for w in dict.fromkeys(words) if w not in _STOPWORDS]


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


def _on_branch(site: StatusSite, names: set[str], conditional: bool, absence: bool) -> bool:
    """Returned under a condition on the requested values, if any are named.

    For an absence ("when the user is not found") the branch must mean *absent*: `if not user`,
    `if user is None`, `x not in y`, an `except` clause, or the `else` of a presence check.
    `if user: return 404` answers the opposite case.
    """
    if not conditional:
        return True
    if absence:
        on_names = [b for b in site.branch if not names or b.condition.identifiers & names]
        return any(_absent(b.condition.text) != b.negated for b in on_names)
    positive = [b for b in site.branch if not b.negated]
    if not positive:
        return False
    return not names or any(b.condition.identifiers & names for b in positive)


def _absent(condition: str) -> bool:
    """Whether a condition holds when the value is absent (None / empty / missing / failed)."""
    if _PRESENT.search(condition):
        return False
    return condition.startswith("except") or _ABSENT.search(condition) is not None


_CONDITIONAL = re.compile(
    r"\b(when|if|unless|whenever|missing|invalid|unknown|not found|doesn'?t exist|does not exist|"
    r"empty|malformed|bad|wrong|already|duplicate|no such|nothing|none|null|outside|between|"
    r"exceed\w*|too (?:long|large|big|many|short)|fails?)\b",
    re.I,
)
_ABSENCE = re.compile(
    r"\b(not found|missing|doesn'?t exist|does not exist|no such|unknown|nonexistent|is none|"
    r"isn'?t there|not there)\b",
    re.I,
)
_PRESENT = re.compile(r"\bis not None\b|!=\s*None\b")
_ABSENT = re.compile(r"\bnot\b|\bis None\b|==\s*None\b|==\s*(?:0|\"\"|''|\[\]|\{\})|\bis False\b")
# "include the book id in the error message" / "mention `sku` in the error".
_MESSAGE = re.compile(
    r"\b(include|mention|contain|add|put|show)\b.*\b(message|error|detail|response|body)\b",
    re.I,
)
_RETURN_INSTEAD = re.compile(
    r"\breturn\w*\s+(?:an?\s+)?(.+?)\s+(?:instead\s+of|rather\s+than)\s+(?:returning\s+)?"
    r"`?([\w\[\]{}()\"']+)`?",
    re.I,
)
# A string literal's plain text is not a value; only its {interpolations} are.
_STRING = re.compile(r"""(["'])(?:\\.|(?!\1).)*\1""")
_INTERPOLATED = re.compile(r"\{([^{}]*)\}")
_VALUE_WORDS = {
    "empty list": "[]",
    "empty dict": "{}",
    "empty dictionary": "{}",
    "empty string": '""',
    "empty tuple": "()",
    "empty set": "set()",
    "none": "None",
    "false": "False",
    "true": "True",
    "zero": "0",
}


def _message(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    """The requested values appear in the error responses (or raised errors) of the target."""
    # Compound names first: "the book id" is `book_id`, not the handler `book`.
    names = sorted(requested_identifiers(requirement, ctx), key=lambda n: "_" not in n)
    sites = [s for s in ctx.after.responses(error_handler_codes(ctx.after_file)) if s.code >= 400]
    errors = [(s.text, s.line) for s in sites] + [
        (r.text, r.line) for r in ctx.after.facts.raises if r.exception
    ]
    if not names or not errors:
        return inconclusive(requirement, "No error response or named value to check.")
    for text, line in errors:
        code = _STRING.sub(lambda m: f" {' '.join(_INTERPOLATED.findall(m.group(0)))} ", text)
        if re.search(rf"\b{re.escape(names[0])}\b", code):
            return RuleOutcome(
                RuleStatus.SATISFIED,
                f"The error includes `{names[0]}`.",
                [located(requirement, "api.message_includes", True, f"`{text}`", ctx.file, line)],
            )
    text, line = errors[0]
    return RuleOutcome(
        RuleStatus.NOT_SATISFIED,
        f"The error message does not include `{names[0]}`.",
        [
            located(
                requirement,
                "api.message_missing_value",
                False,
                f"`{text}` does not mention `{names[0]}`.",
                ctx.file,
                line,
            )
        ],
    )


def _literal(phrase: str) -> str:
    cleaned = phrase.strip("` .").lower()
    return _VALUE_WORDS.get(cleaned, phrase.strip("` ."))


def _return_value(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    """ "Return an empty list instead of None": the new value is returned, the old one is not."""
    match = _RETURN_INSTEAD.search(requirement.description)
    if match is None:
        return inconclusive(requirement, "The requested return value cannot be read.")
    new, old = _literal(match.group(1)), _literal(match.group(2))
    returned = [(r.value or "None", r.line, r.text) for r in ctx.after.facts.returns]
    new_hits = [r for r in returned if r[0] == new]
    old_hits = [r for r in returned if r[0] == old]
    if new_hits and not old_hits:
        value, line, text = new_hits[0]
        return RuleOutcome(
            RuleStatus.SATISFIED,
            f"`{new}` is returned and `{old}` no longer is.",
            [located(requirement, "api.return_value", True, f"`{text}`", ctx.file, line)],
        )
    if old_hits:
        value, line, text = old_hits[0]
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED,
            f"`{old}` is still returned.",
            [
                located(
                    requirement,
                    "api.old_return_value",
                    False,
                    f"`{text}` still returns `{old}`.",
                    ctx.file,
                    line,
                )
            ],
        )
    return inconclusive(requirement, f"`{new}` is not returned literally; cannot tell.")


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
