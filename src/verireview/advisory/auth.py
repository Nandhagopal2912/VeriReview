"""GitHub App authentication (plan §22: prefer an App over broad personal tokens).

The App proves who it is with a short-lived JWT (RS256, signed with its private key), then asks
for an **installation token** per job. That token is narrowed to

- the one repository the job is about (repository isolation: a job for `a/x` cannot read `a/y`),
- the permissions the job needs: contents read, pull requests read, checks write.

Tokens live only in memory, are reused until five minutes before they expire, and are never logged
or stored. The private key is read from settings as a `SecretStr` and only used to sign.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx2 as httpx
import jwt
from pydantic import SecretStr

from verireview.gh.api import RepoRef
from verireview.gh.client import GitHubClient

logger = logging.getLogger(__name__)

# The least privilege advisory mode needs (checked by a test against the request body).
INSTALLATION_PERMISSIONS = {"contents": "read", "pull_requests": "read", "checks": "write"}
JWT_LIFETIME_S = 540  # GitHub allows at most 10 minutes
CLOCK_SKEW_S = 60  # iat in the past, as GitHub recommends
REFRESH_MARGIN = timedelta(minutes=5)


class AppAuthError(RuntimeError):
    """The App could not authenticate (bad key, unknown installation, missing configuration)."""


@dataclass(frozen=True)
class InstallationToken:
    token: SecretStr
    expires_at: datetime

    def fresh(self, now: datetime) -> bool:
        return now < self.expires_at - REFRESH_MARGIN


class GitHubAppAuth:
    def __init__(
        self,
        app_id: int,
        private_key: SecretStr,
        api_url: str = "https://api.github.com",
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._api_url = api_url
        self._timeout_s = timeout_s
        self._transport = transport
        self._clock = clock
        self._tokens: dict[tuple[int, str], InstallationToken] = {}
        self._lock = threading.Lock()

    def app_jwt(self) -> SecretStr:
        now = int(self._clock())
        claims = {"iat": now - CLOCK_SKEW_S, "exp": now + JWT_LIFETIME_S, "iss": str(self._app_id)}
        try:
            encoded = jwt.encode(claims, self._private_key.get_secret_value(), algorithm="RS256")
        except (ValueError, TypeError, jwt.PyJWTError) as exc:
            # Never include the key or the exception text (it may quote the key).
            raise AppAuthError("the GitHub App private key could not sign a JWT") from exc
        return SecretStr(encoded)

    def installation_token(self, installation_id: int, repo: RepoRef) -> SecretStr:
        """A token for one installation, scoped to ``repo`` and INSTALLATION_PERMISSIONS."""
        key = (installation_id, repo.full_name.lower())
        now = datetime.fromtimestamp(self._clock(), tz=UTC)
        with self._lock:
            cached = self._tokens.get(key)
            if cached is not None and cached.fresh(now):
                return cached.token
            with GitHubClient(
                self.app_jwt(),
                api_url=self._api_url,
                timeout_s=self._timeout_s,
                transport=self._transport,
            ) as client:
                payload = client.post_json(
                    f"/app/installations/{installation_id}/access_tokens",
                    {"repositories": [repo.name], "permissions": INSTALLATION_PERMISSIONS},
                )
            token = _parse_token(payload)
            self._tokens[key] = token
            logger.info(
                "installation token issued for installation %s, repository %s (expires %s)",
                installation_id,
                repo.full_name,
                token.expires_at.isoformat(),
            )
            return token.token

    def client_for(self, installation_id: int, repo: RepoRef) -> GitHubClient:
        return GitHubClient(
            self.installation_token(installation_id, repo),
            api_url=self._api_url,
            timeout_s=self._timeout_s,
            transport=self._transport,
        )


def _parse_token(payload: object) -> InstallationToken:
    if not isinstance(payload, dict) or "token" not in payload or "expires_at" not in payload:
        raise AppAuthError("GitHub returned no installation token")
    expires = datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00"))
    return InstallationToken(SecretStr(str(payload["token"])), expires)
