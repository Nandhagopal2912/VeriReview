"""Test doubles for GitHub: a fixture-backed HTTP transport and model factories."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx2 as httpx

from verireview.gh.models import GhCommit, GhReviewComment

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "github" / "acme_shop_pr7"

C1, C2, C3, C4 = ("1" * 40, "2" * 40, "3" * 40, "4" * 40)


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FakeGitHub:
    """Serves the acme/shop#7 fixture over an ``httpx.MockTransport`` and records requests."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        prefix = "/repos/acme/shop"
        routes = {
            f"{prefix}/pulls/7": "pull.json",
            f"{prefix}/pulls/7/comments": "comments.json",
            f"{prefix}/pulls/7/commits": "commits.json",
            f"{prefix}/pulls/7/files": "files.json",
            f"{prefix}/issues/7/timeline": "timeline.json",
            f"{prefix}/compare/{C2}...{C4}": "compare_2_4.json",
            f"{prefix}/pulls": "pulls.json",
            f"{prefix}/license": "license.json",
        }
        if request.method == "POST" and path == "/graphql":
            return httpx.Response(200, json=load_fixture("graphql_threads.json"))
        if path in routes:
            return httpx.Response(200, json=load_fixture(routes[path]))
        if path.startswith(f"{prefix}/contents/"):
            file_path = path.removeprefix(f"{prefix}/contents/")
            target = FIXTURE_DIR / "contents" / request.url.params["ref"] / file_path
            if target.is_file():
                return httpx.Response(200, content=target.read_bytes())
        return httpx.Response(404, json={"message": "Not Found"})


def gh_comment(
    comment_id: int,
    created_at: str,
    *,
    in_reply_to_id: int | None = None,
    original_commit_id: str = C2,
    path: str = "shop/user_service.py",
    body: str = "comment",
    author: str = "rev-bob",
) -> GhReviewComment:
    return GhReviewComment.model_validate(
        {
            "id": comment_id,
            "in_reply_to_id": in_reply_to_id,
            "path": path,
            "original_line": 2,
            "commit_id": C4,
            "original_commit_id": original_commit_id,
            "diff_hunk": "@@ -1 +1 @@",
            "body": body,
            "user": {"login": author},
            "created_at": created_at,
        }
    )


def gh_commit(sha: str, committed_at: str | None, authored_at: str | None = None) -> GhCommit:
    """``authored_at`` defaults to ``committed_at`` (a plain, non-rewritten commit)."""
    authored = authored_at or committed_at
    return GhCommit.model_validate(
        {
            "sha": sha,
            "commit": {
                "message": f"commit {sha[:7]}",
                "author": {"name": "Alice", "date": authored} if authored else None,
                "committer": {"name": "Alice", "date": committed_at} if committed_at else None,
            },
            "author": {"login": "dev-alice"},
        }
    )


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


class FakeGitHubApp(FakeGitHub):
    """FakeGitHub plus the GitHub App endpoints advisory mode uses.

    Issues installation tokens (``POST /app/installations/{id}/access_tokens``) and stores check
    runs (list / create / update), so tests can assert what was published and with which token.
    """

    TOKEN = "ghs_fake_installation_token_0123456789"  # noqa: S105 - test double

    def __init__(self, fail_path: str | None = None) -> None:
        super().__init__()
        self.check_runs: dict[int, dict[str, Any]] = {}
        self.token_requests: list[dict[str, Any]] = []
        self.fail_path = fail_path  # answer 500 on this path (outage simulation)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if self.fail_path and path == self.fail_path:
            self.requests.append(request)
            return httpx.Response(500, json={"message": "boom"})
        if request.method == "POST" and path.startswith("/app/installations/"):
            self.requests.append(request)
            self.token_requests.append(json.loads(request.content))
            return httpx.Response(
                201, json={"token": self.TOKEN, "expires_at": "2099-01-01T00:00:00Z"}
            )
        if path.startswith("/repos/acme/shop/commits/") and path.endswith("/check-runs"):
            self.requests.append(request)
            sha = path.split("/")[5]
            name = request.url.params.get("check_name")
            runs = [
                r for r in self.check_runs.values() if r["head_sha"] == sha and r["name"] == name
            ]
            return httpx.Response(200, json={"total_count": len(runs), "check_runs": runs})
        if path == "/repos/acme/shop/check-runs" and request.method == "POST":
            self.requests.append(request)
            run = {"id": len(self.check_runs) + 1, **json.loads(request.content)}
            self.check_runs[run["id"]] = run
            return httpx.Response(201, json=run)
        if path.startswith("/repos/acme/shop/check-runs/") and request.method == "PATCH":
            self.requests.append(request)
            run_id = int(path.rsplit("/", 1)[1])
            self.check_runs[run_id] = {**self.check_runs[run_id], **json.loads(request.content)}
            return httpx.Response(200, json=self.check_runs[run_id])
        return super()._handle(request)


def rsa_private_key_pem() -> str:
    """A throwaway RSA key generated for the test run (no key material is committed)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


WEBHOOK_DIR = Path(__file__).parent.parent / "fixtures" / "github" / "webhooks"


def load_webhook(name: str) -> bytes:
    return (WEBHOOK_DIR / name).read_bytes()
