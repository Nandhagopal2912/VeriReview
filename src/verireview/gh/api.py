"""Typed GitHub operations used by ingestion, built on :class:`GitHubClient`."""

import re
from typing import Any, Protocol
from urllib.parse import quote

from verireview.gh.client import GitHubClient
from verireview.gh.errors import GitHubNotFoundError
from verireview.gh.models import (
    GhChangedFile,
    GhCommit,
    GhLicense,
    GhPullRequest,
    GhReviewComment,
    GhThreadState,
    GhTimelineEvent,
)

_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")

# The pull-request commits endpoint never returns more than this many commits.
PR_COMMITS_LIMIT = 250

_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          isOutdated
          resolvedBy { login }
          comments(first: 1) { nodes { fullDatabaseId } }
        }
      }
    }
  }
}
"""


class RepoRef:
    """Validated ``owner/name`` pair, so path segments cannot be injected into API URLs."""

    def __init__(self, full_name: str) -> None:
        owner, sep, name = full_name.partition("/")
        if not sep or not _NAME.match(owner) or not _NAME.match(name):
            raise ValueError(f"Expected 'owner/repo', got {full_name!r}")
        self.owner = owner
        self.name = name

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    def __str__(self) -> str:
        return self.full_name


class GitHubReader(Protocol):
    """What ingestion needs from GitHub. Tests provide an in-memory implementation."""

    @property
    def can_read_thread_state(self) -> bool: ...

    def get_pull(self, repo: RepoRef, number: int) -> GhPullRequest: ...

    def list_review_comments(self, repo: RepoRef, number: int) -> list[GhReviewComment]: ...

    def list_pull_commits(self, repo: RepoRef, number: int) -> list[GhCommit]: ...

    def list_timeline(self, repo: RepoRef, number: int) -> list[GhTimelineEvent]: ...

    def list_pull_files(self, repo: RepoRef, number: int) -> list[GhChangedFile]: ...

    def compare_files(self, repo: RepoRef, base: str, head: str) -> list[GhChangedFile] | None: ...

    def get_file(self, repo: RepoRef, path: str, ref: str) -> str | None: ...

    def list_thread_states(self, repo: RepoRef, number: int) -> list[GhThreadState]: ...


class GitHubApi:
    """REST + GraphQL implementation of :class:`GitHubReader`."""

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    @property
    def can_read_thread_state(self) -> bool:
        return self._client.authenticated

    def get_pull(self, repo: RepoRef, number: int) -> GhPullRequest:
        return GhPullRequest.model_validate(self._client.get_json(_pulls(repo, number)))

    def list_review_comments(self, repo: RepoRef, number: int) -> list[GhReviewComment]:
        items = self._client.get_paginated(f"{_pulls(repo, number)}/comments")
        return [GhReviewComment.model_validate(i) for i in items]

    def list_pull_commits(self, repo: RepoRef, number: int) -> list[GhCommit]:
        items = self._client.get_paginated(
            f"{_pulls(repo, number)}/commits", max_items=PR_COMMITS_LIMIT
        )
        return [GhCommit.model_validate(i) for i in items]

    def list_timeline(self, repo: RepoRef, number: int) -> list[GhTimelineEvent]:
        items = self._client.get_paginated(f"/repos/{repo}/issues/{int(number)}/timeline")
        return [GhTimelineEvent.model_validate(i) for i in items]

    def list_pull_files(self, repo: RepoRef, number: int) -> list[GhChangedFile]:
        items = self._client.get_paginated(f"{_pulls(repo, number)}/files")
        return [GhChangedFile.model_validate(i) for i in items]

    def compare_files(self, repo: RepoRef, base: str, head: str) -> list[GhChangedFile] | None:
        """Files changed between two commits, or None if either commit is unreachable."""
        try:
            payload = self._client.get_json(f"/repos/{repo}/compare/{_sha(base)}...{_sha(head)}")
        except GitHubNotFoundError:
            return None
        return [GhChangedFile.model_validate(f) for f in payload.get("files", [])]

    def get_file(self, repo: RepoRef, path: str, ref: str) -> str | None:
        """File contents at a commit, or None if the file or commit does not exist."""
        try:
            return self._client.get_text(
                f"/repos/{repo}/contents/{quote(path, safe='/')}", params={"ref": _sha(ref)}
            )
        except GitHubNotFoundError:
            return None

    def list_pulls(self, repo: RepoRef, max_items: int = 100) -> list[GhPullRequest]:
        """Closed pull requests, most recently updated first (merged or not)."""
        params = {"state": "closed", "sort": "updated", "direction": "desc"}
        items = self._client.get_paginated(f"/repos/{repo}/pulls", params, max_items=max_items)
        return [GhPullRequest.model_validate(i) for i in items]

    def get_license(self, repo: RepoRef) -> GhLicense | None:
        """The repository's detected license, or None when GitHub finds none."""
        try:
            return GhLicense.model_validate(self._client.get_json(f"/repos/{repo}/license"))
        except GitHubNotFoundError:
            return None

    def list_thread_states(self, repo: RepoRef, number: int) -> list[GhThreadState]:
        states: list[GhThreadState] = []
        cursor: str | None = None
        while True:
            variables: dict[str, Any] = {
                "owner": repo.owner,
                "name": repo.name,
                "number": int(number),
                "cursor": cursor,
            }
            data = self._client.graphql(_THREADS_QUERY, variables)
            pull = (data.get("repository") or {}).get("pullRequest")
            if pull is None:
                raise GitHubNotFoundError(f"{repo}#{number}")
            threads = pull["reviewThreads"]
            for node in threads["nodes"]:
                first = node["comments"]["nodes"]
                if not first or first[0].get("fullDatabaseId") is None:
                    continue
                states.append(
                    GhThreadState(
                        root_comment_id=int(first[0]["fullDatabaseId"]),
                        is_resolved=node["isResolved"],
                        is_outdated=node["isOutdated"],
                        resolved_by=(node.get("resolvedBy") or {}).get("login"),
                    )
                )
            if not threads["pageInfo"]["hasNextPage"]:
                return states
            cursor = threads["pageInfo"]["endCursor"]


def _pulls(repo: RepoRef, number: int) -> str:
    return f"/repos/{repo}/pulls/{int(number)}"


def _sha(value: str) -> str:
    if not _SHA.match(value):
        raise ValueError(f"Not a commit SHA: {value!r}")
    return value
