"""GitHub webhook deliveries: signature verification and the events that create work.

Every delivery must carry ``X-Hub-Signature-256: sha256=<hex>``, the HMAC-SHA256 of the *raw*
body under the webhook secret. It is compared in constant time, before anything in the body is
read. Payloads are untrusted data: only the few fields below are taken, each validated
(repository name, positive numbers, 40-hex SHAs), and nothing in them is ever executed or
interpreted as an instruction.

Work comes from three events (owner decisions, Phases 11 and 12):

- ``pull_request_review_thread`` / ``resolved``: verify that thread.
- ``check_run`` / ``rerequested`` on our own check ("Re-run" in the GitHub UI): verify every
  resolved thread of the pull request again.
- ``check_run`` / ``requested_action`` ``confirm_review`` on our own check (Phase 12, human-review
  stage): record that the clicking reviewer confirmed the result.

Everything else (``ping``, unresolved threads, other apps' checks) is acknowledged and ignored.
"""

import hashlib
import hmac
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from verireview.gh.api import RepoRef

SIGNATURE_PREFIX = "sha256="
CONFIRM_ACTION = "confirm_review"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?$")


class InvalidSignatureError(Exception):
    """Missing or wrong signature: the delivery is rejected without being read."""


def sign(secret: str, body: bytes) -> str:
    """The ``X-Hub-Signature-256`` header value GitHub sends for ``body``."""
    return SIGNATURE_PREFIX + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, header: str | None) -> None:
    if not header or not header.startswith(SIGNATURE_PREFIX):
        raise InvalidSignatureError("missing X-Hub-Signature-256")
    if not hmac.compare_digest(sign(secret, body), header):
        raise InvalidSignatureError("signature does not match")


class AdvisoryTask(BaseModel):
    """One unit of advisory work taken from a delivery (validated, nothing else is kept)."""

    kind: Literal["thread", "pull_request", "confirm"]
    installation_id: int = Field(gt=0)
    repository: str
    pull_number: int = Field(gt=0)
    comment_id: int | None = Field(default=None, gt=0)  # any comment of the thread
    head_sha: str | None = None
    actor: str | None = None  # GitHub login of the reviewer who confirmed (kind "confirm")

    @field_validator("actor")
    @classmethod
    def _login(cls, value: str | None) -> str | None:
        if value is not None and not _LOGIN.match(value):
            raise ValueError("not a GitHub login")
        return value

    @field_validator("repository")
    @classmethod
    def _repo(cls, value: str) -> str:
        RepoRef(value)
        return value

    @field_validator("head_sha")
    @classmethod
    def _sha(cls, value: str | None) -> str | None:
        if value is not None and not _SHA.match(value):
            raise ValueError("head_sha must be 40 hex characters")
        return value


def tasks_from_event(event: str, payload: dict[str, Any], check_name: str) -> list[AdvisoryTask]:
    """The advisory work a delivery asks for ([] = acknowledge and ignore)."""
    action = payload.get("action")
    installation = (payload.get("installation") or {}).get("id")
    repository = (payload.get("repository") or {}).get("full_name")
    if not installation or not repository:
        return []

    if event == "pull_request_review_thread" and action == "resolved":
        thread = payload.get("thread") or {}
        comments = thread.get("comments") or []
        pull = payload.get("pull_request") or {}
        if not comments or "number" not in pull:
            return []
        return [
            AdvisoryTask(
                kind="thread",
                installation_id=installation,
                repository=repository,
                pull_number=pull["number"],
                comment_id=comments[0].get("id"),
                head_sha=(pull.get("head") or {}).get("sha"),
            )
        ]

    if event == "check_run" and action in ("rerequested", "requested_action"):
        run = payload.get("check_run") or {}
        if run.get("name") != check_name:
            return []
        if action == "requested_action":
            identifier = (payload.get("requested_action") or {}).get("identifier")
            if identifier != CONFIRM_ACTION:
                return []
            return [
                AdvisoryTask(
                    kind="confirm",
                    installation_id=installation,
                    repository=repository,
                    pull_number=pr["number"],
                    head_sha=run.get("head_sha"),
                    actor=(payload.get("sender") or {}).get("login"),
                )
                for pr in run.get("pull_requests") or []
                if isinstance(pr, dict) and "number" in pr
            ]
        return [
            AdvisoryTask(
                kind="pull_request",
                installation_id=installation,
                repository=repository,
                pull_number=pr["number"],
                head_sha=run.get("head_sha"),
            )
            for pr in run.get("pull_requests") or []
            if isinstance(pr, dict) and "number" in pr
        ]
    return []
