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
