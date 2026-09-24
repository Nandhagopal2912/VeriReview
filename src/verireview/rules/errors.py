"""Error-handling rule (plan §12): "Handle database failure."

The request is turned into a checklist, each item verified structurally in the target code:

- catch E        a handler for E (or a broad handler) that does something: not just `pass`, not
                 just a bare `raise`, and around the call the request names, if it names one
- retry          the protected call can run again (a loop around it, or it is called twice)
- raise F        a `raise F(...)` that was not there before
- chain          a `raise … from err` (keeps the original traceback)
- log            a logging call inside a handler or branch (`logger.exception` / `exc_info` when
                 the traceback is asked for; the requested values, if named)
- re-raise       a handler that raises again after doing its work
- fall back to X a handler (or guard) that returns X ("an empty dict" → `{}`)
- only E         no broad handler (`except Exception`) is left ("catch only …, let others
                 propagate")
- not swallowed  no handler just passes ("don't swallow this silently")
- cleanup        a `finally:` that closes/releases, or a new `with` block ("make sure it gets
                 closed even if …")
- generic        ("handle that case") a new handler, or a new guard that returns/raises

`with contextlib.suppress(E)` counts as a handler that deliberately ignores E, which is what an
"ignore …" request asks for. All items must hold. When nothing handles the failure but the code
now runs inside a context manager defined elsewhere (`with db_guard():`), whether that handles it
cannot be seen: inconclusive, not a verdict. ADR-001: every item already true before the comment
→ already present.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from verireview.contracts import Evidence, Requirement
from verireview.requirements import lexicon as lx
from verireview.rules.analysis import HandlerInfo, Scope
from verireview.rules.base import (
    RuleContext,
    RuleOutcome,
    RuleStatus,
    located,
    quoted_identifiers,
    requested_identifiers,
    unlocated,
)

_BROAD = frozenset({"Exception", "BaseException", ""})
# Idioms that make an exception impossible instead of catching it.
_AVOIDANCE_IDIOMS = {"KeyError": ".get"}
_LOG_CALL = re.compile(r"^(logger|logging|log|LOGGER|_logger|self\.log(ger)?)\.\w+$")
# An *imperative* raise ("… and raise a `ServiceError`"), not a description of what the code
# does ("`get` can raise `RequestException`", "`profiles[id]` raises KeyError"): those ask for it
# to be caught. Only the verb is case-insensitive: [A-Z] must not match "raise *after* logging".
_RAISED = re.compile(
    r"(?:^|[;:,]\s*|\b(?:and|then|to|should|must|please|instead|or)\s+)"
    r"(?i:raise|throw)\s+(?:an?\s+)?`?([A-Z]\w*)"
)
_LOG_WITH = re.compile(r"\bwith\s+(?:the\s+)?(.+?)(?=\)|,|\.|;|\bbefore\b|\bafter\b|$)", re.I)
_FALLBACK = re.compile(r"\b(?:fall\s*back\s+to|return)\s+`?([\w.()\[\]{}'\"-]+)`?", re.I)
_EMPTY_VALUE = re.compile(r"\ban?\s+empty\s+(dict(?:ionary)?|list|string|str|tuple|set)\b", re.I)
_EMPTY_LITERAL = {
    "dict": "{}",
    "dictionary": "{}",
    "list": "[]",
    "string": '""',
    "str": '""',
    "tuple": "()",
    "set": "set()",
}
_CHAIN = re.compile(r"\braise\b[^.;]*\bfrom\b|\bfrom (?:err|e|exc|error)\b|\bchain", re.I)
_TRACEBACK = re.compile(r"\b(traceback|stack ?trace|exc_info)\b", re.I)
_NARROW = re.compile(
    r"\bonly\b|\bnot every (?:exception|error)|\bpropagate|\btoo broad|\bnarrow|\bbare except",
    re.I,
)
_NO_SWALLOW = re.compile(r"\bswallow\w*|\bsilently\b", re.I)
_IGNORE = re.compile(r"\bignor\w*|\bsuppress\w*|\bskip\b", re.I)
_CLEANUP = re.compile(
    r"\bclos(e|ed|es)\b|\breleas\w*|\bclean(ed)? ?up|\beven if\b|\bfinally\b", re.I
)
_CLEANUP_CALL = re.compile(r"(close|release|unlock|cleanup|clean_up|shutdown|rollback|stop)$")
# Context managers whose behaviour is known; anything else defined elsewhere may handle errors.
_KNOWN_CONTEXTS = frozenset(
    {"open", "suppress", "patch", "raises", "lock", "acquire", "TemporaryDirectory", "closing"}
)

_Result = tuple[bool | None, str, int | None]  # (ok, detail, line); ok None = cannot tell


@dataclass(frozen=True)
class _Check:
    name: str
    test: Callable[[Scope], _Result]


def error_handling_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    checks = _checklist(requirement, ctx)
    evidence: list[Evidence] = []
    failed: list[str] = []
    unknown: list[str] = []
    already = True
    for check in checks:
        ok, detail, line = check.test(ctx.after)
        was_ok, _, _ = check.test(ctx.before)
        already = already and ok is True and was_ok is True
        if ok is False:
            failed.append(check.name)
        elif ok is None:
            unknown.append(check.name)
        kind = f"error_handling.{check.name.replace(' ', '_')}"
        if line is not None:
            evidence.append(located(requirement, kind, ok, detail, ctx.file, line))
        else:
            evidence.append(unlocated(requirement, kind, ok, detail, "absence has no location"))

    if failed:
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED, "Missing: " + ", ".join(failed) + ".", evidence
        )
    if unknown:
        return RuleOutcome(
            RuleStatus.INCONCLUSIVE,
            "Cannot tell whether " + ", ".join(unknown) + " is done (delegated elsewhere).",
            evidence,
        )
    if already:
        evidence.append(
            unlocated(
                requirement,
                "already_present",
                True,
                "The requested handling already existed before the comment (ADR-001).",
                "state predates the comment",
            )
        )
    return RuleOutcome(
        RuleStatus.SATISFIED,
        "The requested error handling is present.",
        evidence,
        already_present=already,
    )


def _checklist(requirement: Requirement, ctx: RuleContext) -> list[_Check]:
    text = _EMPTY_VALUE.sub(lambda m: _EMPTY_LITERAL[m.group(1).lower()], requirement.description)
    raised = [m.group(1) for m in _RAISED.finditer(text)]
    target_name = (requirement.target or "").split(".")[-1]
    # An exception the request says to *raise* is not one it asks to catch.
    target = (
        requirement.target
        if target_name and lx.EXCEPTION_NAME.fullmatch(target_name) and target_name not in raised
        else None
    )
    caught = (
        [target.split(".")[-1]]
        if target
        else [n for n in dict.fromkeys(lx.EXCEPTION_NAME.findall(text)) if n not in raised]
    )
    if not caught and re.search(r"\b(catch|handle)\b", text, re.I):
        # "`get` can raise `RequestException`; catch it": the exception is named elsewhere in
        # the comment, and "it" refers to it.
        in_comment = {m.group(1) for m in _RAISED.finditer(ctx.comment)}
        caught = [
            n for n in dict.fromkeys(lx.EXCEPTION_NAME.findall(ctx.comment)) if n not in in_comment
        ]
    allow_swallow = _IGNORE.search(text) is not None
    names = [n for n in requested_identifiers(requirement, ctx) if n not in caught + raised]
    protected = _named_calls(ctx)
    checks: list[_Check] = [
        _catch(
            e, names, ctx, allow_swallow, protected, reraise_ok=bool(re.search(r"re-?rais", text))
        )
        for e in caught
    ]
    if re.search(r"\bretr(y|ies|ied)\b", text, re.I):
        checks.append(_Check("retry", _retry))
    checks += [_raise(e) for e in raised]
    if _CHAIN.search(text):
        checks.append(_Check("chain", _chain))
    if re.search(r"\blog", text, re.I):
        checks.append(_log(_log_values(text, ctx), traceback=bool(_TRACEBACK.search(text))))
    if re.search(r"\bre-?rais", text, re.I):
        checks.append(_Check("re-raise", _reraise))
    fallback = _FALLBACK.search(text)
    if fallback and not raised:
        checks.append(_fallback(fallback.group(1).rstrip(".,)")))
    if _NARROW.search(text) and caught:
        checks.append(_Check("only the named exception", _no_broad))
    if _NO_SWALLOW.search(text) and not allow_swallow:
        checks.append(_Check("not swallowed", _not_swallowed))
    if _CLEANUP.search(text):
        checks.append(_cleanup(ctx))
    if not checks:
        checks.append(_generic(names, ctx, allow_swallow))
    return checks


def _log_values(text: str, ctx: RuleContext) -> list[str]:
    """Identifiers named in "log … with the customer id": only the "with …" phrase counts."""
    match = _LOG_WITH.search(text)
    if not match:
        return []
    known = ctx.before_file.identifiers | ctx.after_file.identifiers
    words = re.findall(r"[A-Za-z_]\w*", match.group(1))
    candidates = words + [f"{a}_{b}".lower() for a, b in zip(words, words[1:], strict=False)]
    return [c for c in dict.fromkeys(candidates) if c in known]


def _named_calls(ctx: RuleContext) -> list[str]:
    """Calls the comment names (`requests.get`) that exist in the code: what must be protected."""
    callees = {c.callee for c in ctx.after.facts.calls} | {c.callee for c in ctx.before.facts.calls}
    return [q for q in quoted_identifiers(ctx.comment) if "." in q and q in callees]


def _delegated_context(ctx: RuleContext) -> tuple[str, int] | None:
    """A new `with helper():` whose definition is not in this file (it may handle the failure)."""
    before = {text for _, text, _ in ctx.before.with_contexts()}
    defined = ctx.after_file.defined_names()
    for callee, text, line in ctx.after.with_contexts():
        name = callee.split(".")[-1]
        if text not in before and name not in defined and name not in _KNOWN_CONTEXTS:
            return name, line
    return None


def _unknown_or(ctx: RuleContext, failure: _Result) -> _Result:
    delegated = _delegated_context(ctx)
    if delegated is None:
        return failure
    name, line = delegated
    return None, f"The code now runs inside `with {name}(…)`, defined elsewhere.", line


# ---------------------------------------------------------------- checks


def _catch(
    exception: str,
    names: list[str],
    ctx: RuleContext,
    allow_swallow: bool,
    protected: list[str],
    reraise_ok: bool,
) -> _Check:
    avoided_by = _AVOIDANCE_IDIOMS.get(exception)
    before_idiom_calls = {c.text for c in ctx.before.facts.calls}

    def test(scope: Scope) -> _Result:
        for h in scope.handlers():
            caught = {e.split(".")[-1] for e in h.handler.exceptions} or {""}
            if exception not in caught and not caught & _BROAD:
                continue
            if h.handler.swallows and not allow_swallow:
                return False, f"`{h.handler.text}` swallows the exception (`pass`).", h.line
            if _only_reraises(h) and not reraise_ok:
                return False, f"`{h.handler.text}` only re-raises: nothing is handled.", h.line
            if protected and not any(
                c.callee in protected or c.callee.endswith(tuple("." + p for p in protected))
                for c in h.protected_calls
            ):
                wanted = ", ".join(f"`{p}`" for p in protected)
                return False, f"`{h.handler.text}` does not protect {wanted}.", h.line
            return True, f"`{h.handler.text}` handles `{exception}`.", h.line
        for g in scope.guards():
            if g.rejects and names and g.condition.identifiers & set(names):
                return True, f"Guard `{g.condition.text}` prevents the failure.", g.line
        if avoided_by is not None:
            # A *new* idiomatic call that cannot raise, e.g. `config.get(key)` for KeyError.
            for c in scope.facts.calls:
                if c.callee.endswith(avoided_by) and c.text not in before_idiom_calls:
                    return True, f"`{c.text}` avoids `{exception}` altogether.", c.line
        return _unknown_or(ctx, (False, f"No handler for `{exception}`.", None))

    return _Check(f"catch {exception}", test)


def _only_reraises(h: HandlerInfo) -> bool:
    return (
        h.handler.reraises
        and not h.calls
        and not h.returns
        and all(r.exception is None for r in h.raises)
    )


def _retry(scope: Scope) -> _Result:
    for h in scope.handlers():
        for call in h.protected_calls:
            same = [c for c in scope.facts.calls if c.callee == call.callee]
            if len(same) >= 2 or scope.loops_containing(call.line):
                return True, f"`{call.callee}` is attempted again after a failure.", call.line
    return False, "The failing call is never retried.", None


def _raise(exception: str) -> _Check:
    def test(scope: Scope) -> _Result:
        for r in scope.facts.raises:
            if r.exception and r.exception.split(".")[-1] == exception:
                return True, f"`{r.text}` raises `{exception}`.", r.line
        return False, f"`{exception}` is never raised.", None

    return _Check(f"raise {exception}", test)


def _chain(scope: Scope) -> _Result:
    for r in scope.facts.raises:
        if r.exception and " from " in r.text and not r.text.endswith("from None"):
            return True, f"`{r.text}` keeps the original exception as its cause.", r.line
    return False, "No `raise … from err`: the original traceback is not chained.", None


def _log(names: list[str], traceback: bool = False) -> _Check:
    def test(scope: Scope) -> _Result:
        # Failure paths: exception handlers, then conditional branches ("when the cache misses").
        failure_path_calls = [c for h in scope.handlers() for c in h.calls] + [
            c for g in scope.guards() for c in g.calls
        ]
        for call in (c for c in failure_path_calls if _LOG_CALL.match(c.callee)):
            missing = [n for n in names if n not in call.text]
            if missing:
                listed = ", ".join(f"`{n}`" for n in missing)
                return False, f"`{call.text}` does not include {listed}.", call.line
            if traceback and not (call.callee.endswith(".exception") or "exc_info" in call.text):
                return (
                    False,
                    f"`{call.text}` logs without the traceback (`logger.exception` or "
                    "`exc_info=True`).",
                    call.line,
                )
            return True, f"`{call.text}` logs the failure.", call.line
        return False, "No logging call on a failure path (handler or conditional branch).", None

    return _Check("log", test)


def _reraise(scope: Scope) -> _Result:
    for h in scope.handlers():
        if h.handler.reraises:
            return True, f"`{h.handler.text}` re-raises.", h.line
    return False, "No handler re-raises the exception.", None


def _fallback(value: str) -> _Check:
    variants = {value, value.replace('"', "'")}

    def returns(values: list[str]) -> bool:
        return any(v in r for v in variants for r in values)

    def test(scope: Scope) -> _Result:
        for h in scope.handlers():
            if returns([r.value for r in h.returns]):
                return True, f"`{h.handler.text}` falls back to `{value}`.", h.line
        for g in scope.guards():
            if returns([r.value for r in g.returns]):
                return True, f"Guard `{g.condition.text}` returns `{value}`.", g.line
        return False, f"Nothing falls back to `{value}`.", None

    return _Check(f"fall back to {value}", test)


def _no_broad(scope: Scope) -> _Result:
    handlers = [h for h in scope.handlers() if not h.handler.text.startswith("with ")]
    for h in handlers:
        caught = {e.split(".")[-1] for e in h.handler.exceptions} or {""}
        if caught & _BROAD:
            return False, f"`{h.handler.text}` still catches every exception.", h.line
    if not handlers:
        return False, "No exception handler.", None
    return True, "Only specific exceptions are caught.", handlers[0].line


def _not_swallowed(scope: Scope) -> _Result:
    handlers = scope.handlers()
    for h in handlers:
        if h.handler.swallows:
            return False, f"`{h.handler.text}` still swallows the exception.", h.line
    if not handlers:
        return False, "No exception handler.", None
    return (
        True,
        f"`{handlers[0].handler.text}` does something with the exception.",
        handlers[0].line,
    )


def _cleanup(ctx: RuleContext) -> _Check:
    before_with = {text for _, text, _ in ctx.before.with_contexts()}
    before_finally = {c.text for c in ctx.before.finally_calls()}

    def test(scope: Scope) -> _Result:
        for c in scope.finally_calls():
            if _CLEANUP_CALL.search(c.callee.split(".")[-1]):
                return True, f"`{c.text}` runs in `finally:`, even on failure.", c.line
        for _callee, text, line in scope.with_contexts():
            if scope is ctx.before or text not in before_with:
                return True, f"`with {text}` releases the resource even on failure.", line
        if before_finally and scope is ctx.before:
            return True, "Cleanup already runs in `finally:`.", None
        return False, "Nothing releases the resource on failure (no `finally:` or `with`).", None

    return _Check("cleanup", test)


def _generic(names: list[str], ctx: RuleContext, allow_swallow: bool) -> _Check:
    before_handlers = {h.handler.text for h in ctx.before.handlers()}
    before_guards = {g.condition.text for g in ctx.before.guards()}

    def test(scope: Scope) -> _Result:
        for h in scope.handlers():
            if h.handler.text not in before_handlers and (allow_swallow or not h.handler.swallows):
                return True, f"New handler `{h.handler.text}`.", h.line
        for g in scope.guards():
            if (
                g.rejects
                and g.condition.text not in before_guards
                and (not names or g.condition.identifiers & set(names))
            ):
                return True, f"New guard `{g.condition.text}`.", g.line
        return _unknown_or(ctx, (False, "No new exception handler or guard.", None))

    return _Check("handling", test)
