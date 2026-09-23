"""Low-level GitHub HTTP client: auth, retries, rate limits, pagination.

Only relative API paths are accepted, so a caller can never redirect the token to another host.
"""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx2 as httpx
from pydantic import SecretStr

from verireview import __version__
from verireview.gh.errors import (
    GitHubAuthRequiredError,
    GitHubGraphQLError,
    GitHubNotFoundError,
    GitHubRateLimitedError,
    GitHubRequestError,
)

logger = logging.getLogger(__name__)

JSON_ACCEPT = "application/vnd.github+json"
RAW_ACCEPT = "application/vnd.github.raw+json"
API_VERSION = "2022-11-28"

# Wait out a rate limit only if it resets soon; otherwise fail fast and let the caller decide.
MAX_RATE_LIMIT_WAIT_S = 60.0
RETRYABLE_STATUS = frozenset({500, 502, 503, 504})


class GitHubClient:
    def __init__(
        self,
        token: SecretStr | None,
        api_url: str = "https://api.github.com",
        timeout_s: float = 30.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        headers = {
            "Accept": JSON_ACCEPT,
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": f"verireview/{__version__}",
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token.get_secret_value()}"
        self._has_token = token is not None
        self._max_retries = max_retries
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=api_url.rstrip("/"),
            headers=headers,
            timeout=timeout_s,
            transport=transport,
            follow_redirects=False,
        )

    @property
    def authenticated(self) -> bool:
        return self._has_token

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- public API ---------------------------------------------------------------------------

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params).json()

    def get_text(self, path: str, params: dict[str, Any] | None = None) -> str:
        response = self._request("GET", path, params=params, accept=RAW_ACCEPT)
        return response.content.decode("utf-8", errors="replace")

    def get_paginated(
        self, path: str, params: dict[str, Any] | None = None, max_items: int = 3000
    ) -> list[Any]:
        """Follow ``Link: rel="next"`` until exhausted or ``max_items`` is reached."""
        items: list[Any] = []
        query: dict[str, Any] | None = {"per_page": 100, **(params or {})}
        next_path: str | None = path
        while next_path is not None and len(items) < max_items:
            response = self._request("GET", next_path, params=query)
            page = response.json()
            if not isinstance(page, list):
                raise GitHubRequestError(response.status_code, path)
            items.extend(page)
            next_path = _next_link(response)
            # The next link already carries the full query string. Pass None, not {}:
            # an empty mapping would replace that query and loop on page 1 forever.
            query = None
        return items[:max_items]

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if not self._has_token:
            raise GitHubAuthRequiredError("GitHub GraphQL requires VERIREVIEW_GITHUB_TOKEN")
        response = self._request("POST", "/graphql", json={"query": query, "variables": variables})
        payload = response.json()
        if payload.get("errors"):
            messages = "; ".join(str(e.get("message", "?")) for e in payload["errors"])
            raise GitHubGraphQLError(messages)
        data: dict[str, Any] = payload["data"]
        return data

    # -- internals ----------------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
        accept: str = JSON_ACCEPT,
    ) -> httpx.Response:
        path = self._relative(path)
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._http.request(
                    method, path, params=params, json=json, headers={"Accept": accept}
                )
            except httpx.TransportError as exc:
                if attempt > self._max_retries:
                    raise GitHubRequestError(0, path) from exc
                self._backoff(attempt, path, type(exc).__name__)
                continue

            logger.debug("GitHub %s %s -> %s", method, path, response.status_code)

            if response.status_code < 400:
                return response
            if response.status_code == 404:
                raise GitHubNotFoundError(path)
            if _is_rate_limited(response):
                wait_s = _rate_limit_wait_s(response)
                if (
                    wait_s is not None
                    and wait_s <= MAX_RATE_LIMIT_WAIT_S
                    and attempt <= self._max_retries
                ):
                    logger.warning("GitHub rate limited; waiting %.0fs", wait_s)
                    self._sleep(wait_s)
                    continue
                raise GitHubRateLimitedError(_reset_at(response))
            if response.status_code in RETRYABLE_STATUS and attempt <= self._max_retries:
                self._backoff(attempt, path, str(response.status_code))
                continue
            raise GitHubRequestError(response.status_code, path)

    def _backoff(self, attempt: int, path: str, reason: str) -> None:
        delay = float(2 ** (attempt - 1))
        logger.warning("GitHub %s failed (%s); retry %d in %.0fs", path, reason, attempt, delay)
        self._sleep(delay)

    def _relative(self, path: str) -> str:
        """Accept '/repos/...' or an absolute URL on the configured API host (from Link headers)."""
        base = str(self._http.base_url).rstrip("/")
        if path.startswith(base + "/"):
            return path[len(base) :]
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError(f"Refusing non-API path: {path!r}")
        return path


def _next_link(response: httpx.Response) -> str | None:
    for part in response.headers.get("link", "").split(","):
        segments = [s.strip() for s in part.split(";")]
        if len(segments) >= 2 and 'rel="next"' in segments[1:]:
            return segments[0].strip("<>")
    return None


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    return response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers


def _reset_at(response: httpx.Response) -> datetime | None:
    reset = response.headers.get("x-ratelimit-reset")
    return datetime.fromtimestamp(int(reset), tz=UTC) if reset and reset.isdigit() else None


def _rate_limit_wait_s(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return float(retry_after)
    reset_at = _reset_at(response)
    if reset_at is None:
        return None
    return max(0.0, (reset_at - datetime.now(UTC)).total_seconds()) + 1.0
