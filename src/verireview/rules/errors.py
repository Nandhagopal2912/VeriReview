"""Error-handling rule (plan §12): "Handle database failure."

The request is turned into a checklist, each item verified structurally in the target code:

- catch E        a handler for E (or a broad handler) whose body does something (not just `pass`)
- retry          the protected call can run again (a loop around it, or it is called twice)
- raise F        a `raise F(...)` that was not there before
- log            a logging call inside a handler (with the requested values, if named)
- re-raise       a handler that raises again after doing its work
- fall back to X a handler (or guard) that returns X
- generic        ("handle that case") a new handler, or a new guard that returns/raises

All items must hold. ADR-001: every item already true before the comment → already present.
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
    requested_identifiers,
    unlocated,
)

_BROAD = frozenset({"Exception", "BaseException", ""})
# Idioms that make an exception impossible instead of catching it.
_AVOIDANCE_IDIOMS = {"KeyError": ".get"}
_LOG_CALL = re.compile(r"^(logger|logging|log|LOGGER|_logger|self\.log(ger)?)\.\w+$")
# Only the verb is case-insensitive: with re.I, [A-Z] would also match "raise *after* logging".
_RAISED = re.compile(r"\b(?i:raise|throw)s?\s+(?:an?\s+)?`?([A-Z]\w*)")
_LOG_WITH = re.compile(r"\bwith\s+(?:the\s+)?(.+?)(?=\)|,|\.|;|\bbefore\b|\bafter\b|$)", re.I)
_FALLBACK = re.compile(r"\b(?:fall\s*back\s+to|return)\s+`?([\w.()\[\]'\"-]+)`?", re.I)


@dataclass(frozen=True)
class _Check:
    name: str
    test: Callable[[Scope], tuple[bool, str, int | None]]  # (ok, detail, line)


def error_handling_rule(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    checks = _checklist(requirement, ctx)
    evidence: list[Evidence] = []
    failed: list[str] = []
    already = True
    for check in checks:
        ok, detail, line = check.test(ctx.after)
        was_ok, _, _ = check.test(ctx.before)
        already = already and ok and was_ok
        if not ok:
            failed.append(check.name)
        kind = f"error_handling.{check.name.replace(' ', '_')}"
        if line is not None:
            evidence.append(located(requirement, kind, ok, detail, ctx.file, line))
        else:
            evidence.append(unlocated(requirement, kind, ok, detail, "absence has no location"))

    if failed:
        return RuleOutcome(
            RuleStatus.NOT_SATISFIED, "Missing: " + ", ".join(failed) + ".", evidence
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
    text = requirement.description
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
    names = [n for n in requested_identifiers(requirement, ctx) if n not in caught + raised]
    checks: list[_Check] = [_catch(e, names, ctx.before) for e in caught]
    if re.search(r"\bretr(y|ies|ied)\b", text, re.I):
        checks.append(_Check("retry", _retry))
    checks += [_raise(e, ctx.before) for e in raised]
    if re.search(r"\blog", text, re.I):
        checks.append(_log(_log_values(text, ctx)))
    if re.search(r"\bre-?rais", text, re.I):
        checks.append(_Check("re-raise", _reraise))
    fallback = _FALLBACK.search(text)
    if fallback and not raised:
        checks.append(_fallback(fallback.group(1).rstrip(".,)")))
    if not checks:
        checks.append(_generic(names, ctx.before))
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


# ---------------------------------------------------------------- checks


def _catch(exception: str, names: list[str], before: Scope) -> _Check:
    avoided_by = _AVOIDANCE_IDIOMS.get(exception)
    before_idiom_calls = {c.text for c in before.facts.calls}

    def test(scope: Scope) -> tuple[bool, str, int | None]:
        for h in scope.handlers():
            caught = {e.split(".")[-1] for e in h.handler.exceptions} or {""}
            if exception in caught or caught & _BROAD:
                if h.handler.swallows:
                    return False, f"`{h.handler.text}` swallows the exception (`pass`).", h.line
                return True, f"`{h.handler.text}` handles `{exception}`.", h.line
        for g in scope.guards():
            if g.rejects and names and g.condition.identifiers & set(names):
                return True, f"Guard `{g.condition.text}` prevents the failure.", g.line
        if avoided_by is not None:
            # A *new* idiomatic call that cannot raise, e.g. `config.get(key)` for KeyError.
            for c in scope.facts.calls:
                if c.callee.endswith(avoided_by) and c.text not in before_idiom_calls:
                    return True, f"`{c.text}` avoids `{exception}` altogether.", c.line
        return False, f"No handler for `{exception}`.", None

    return _Check(f"catch {exception}", test)


def _retry(scope: Scope) -> tuple[bool, str, int | None]:
    for h in scope.handlers():
        for call in h.protected_calls:
            same = [c for c in scope.facts.calls if c.callee == call.callee]
            if len(same) >= 2 or scope.loops_containing(call.line):
                return True, f"`{call.callee}` is attempted again after a failure.", call.line
    return False, "The failing call is never retried.", None


def _raise(exception: str, before: Scope) -> _Check:
    def test(scope: Scope) -> tuple[bool, str, int | None]:
        for r in scope.facts.raises:
            if r.exception and r.exception.split(".")[-1] == exception:
                return True, f"`{r.text}` raises `{exception}`.", r.line
        return False, f"`{exception}` is never raised.", None

    return _Check(f"raise {exception}", test)


def _log(names: list[str]) -> _Check:
    def test(scope: Scope) -> tuple[bool, str, int | None]:
        # Failure paths: exception handlers, then conditional branches ("when the cache misses").
        failure_path_calls = [c for h in scope.handlers() for c in h.calls] + [
            c for g in scope.guards() for c in g.calls
        ]
        for call in (c for c in failure_path_calls if _LOG_CALL.match(c.callee)):
            missing = [n for n in names if n not in call.text]
            if missing:
                listed = ", ".join(f"`{n}`" for n in missing)
                return False, f"`{call.text}` does not include {listed}.", call.line
            return True, f"`{call.text}` logs the failure.", call.line
        return False, "No logging call on a failure path (handler or conditional branch).", None

    return _Check("log", test)


def _reraise(scope: Scope) -> tuple[bool, str, int | None]:
    for h in scope.handlers():
        if h.handler.reraises:
            return True, f"`{h.handler.text}` re-raises.", h.line
    return False, "No handler re-raises the exception.", None


def _fallback(value: str) -> _Check:
    def test(scope: Scope) -> tuple[bool, str, int | None]:
        for h in scope.handlers():
            if _returns(h, value):
                return True, f"`{h.handler.text}` falls back to `{value}`.", h.line
        for g in scope.guards():
            if any(value in r.value for r in g.returns):
                return True, f"Guard `{g.condition.text}` returns `{value}`.", g.line
        return False, f"Nothing falls back to `{value}`.", None

    return _Check(f"fall back to {value}", test)


def _returns(handler: HandlerInfo, value: str) -> bool:
    return any(value in r.value for r in handler.returns)


def _generic(names: list[str], before: Scope) -> _Check:
    before_handlers = {h.handler.text for h in before.handlers()}
    before_guards = {g.condition.text for g in before.guards()}

    def test(scope: Scope) -> tuple[bool, str, int | None]:
        for h in scope.handlers():
            if h.handler.text not in before_handlers and not h.handler.swallows:
                return True, f"New handler `{h.handler.text}`.", h.line
        for g in scope.guards():
            if (
                g.rejects
                and g.condition.text not in before_guards
                and (not names or g.condition.identifiers & set(names))
            ):
                return True, f"New guard `{g.condition.text}`.", g.line
        return False, "No new exception handler or guard.", None

    return _Check("handling", test)
