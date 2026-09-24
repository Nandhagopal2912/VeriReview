"""Dashboard sign-in (Phase 13, owner decision: one operator token, off by default).

- No ``VERIREVIEW_DASHBOARD_TOKEN`` → every dashboard URL answers 404, as if it did not exist.
- The operator signs in with the token (constant-time comparison). The cookie holds an expiry and
  an HMAC over it, under a key derived from the token, never the token itself. It is
  ``HttpOnly``, ``SameSite=Strict``, path-scoped to ``/dashboard``, and ``Secure`` over HTTPS.
  Changing the token invalidates every session.
- Failed sign-ins are rate-limited per client address (10 per 5 minutes).
"""

import hashlib
import hmac
import threading
import time
from collections import defaultdict, deque

from pydantic import SecretStr

COOKIE = "verireview_dashboard"
_KEY_CONTEXT = b"verireview-dashboard-session-v1"
MAX_FAILURES = 10
FAILURE_WINDOW_S = 300.0


def _key(token: SecretStr) -> bytes:
    return hashlib.sha256(_KEY_CONTEXT + token.get_secret_value().encode()).digest()


def token_matches(token: SecretStr, candidate: str) -> bool:
    return hmac.compare_digest(
        token.get_secret_value().encode(), candidate.encode("utf-8", errors="replace")
    )


def issue_session(token: SecretStr, hours: int, now: float | None = None) -> str:
    expires = int((now if now is not None else time.time()) + hours * 3600)
    mac = hmac.new(_key(token), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{mac}"


def session_valid(token: SecretStr, value: str | None, now: float | None = None) -> bool:
    if not value or "." not in value:
        return False
    expires, _, mac = value.partition(".")
    if not expires.isdigit():
        return False
    expected = hmac.new(_key(token), expires.encode(), hashlib.sha256).hexdigest()
    current = now if now is not None else time.time()
    return hmac.compare_digest(expected, mac) and int(expires) > current


class LoginLimiter:
    """At most ``MAX_FAILURES`` failed sign-ins per client in ``FAILURE_WINDOW_S`` seconds."""

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def blocked(self, client: str, now: float | None = None) -> bool:
        current = now if now is not None else time.time()
        with self._lock:
            failures = self._failures[client]
            while failures and failures[0] < current - FAILURE_WINDOW_S:
                failures.popleft()
            return len(failures) >= MAX_FAILURES

    def fail(self, client: str, now: float | None = None) -> None:
        with self._lock:
            self._failures[client].append(now if now is not None else time.time())

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


limiter = LoginLimiter()
