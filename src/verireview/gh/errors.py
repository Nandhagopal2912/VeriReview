"""GitHub access errors. Messages never contain tokens or response bodies."""

from datetime import datetime


class GitHubError(Exception):
    """Base class for all GitHub access failures."""


class GitHubNotFoundError(GitHubError):
    """404: the resource does not exist or is not visible with the current credentials."""


class GitHubAuthRequiredError(GitHubError):
    """The operation (e.g. GraphQL) needs a token and none is configured."""


class GitHubRateLimitedError(GitHubError):
    def __init__(self, reset_at: datetime | None) -> None:
        self.reset_at = reset_at
        when = reset_at.isoformat() if reset_at else "unknown"
        super().__init__(f"GitHub rate limit exceeded; resets at {when}")


class GitHubRequestError(GitHubError):
    def __init__(self, status_code: int, path: str) -> None:
        self.status_code = status_code
        super().__init__(f"GitHub request failed with HTTP {status_code}: {path}")


class GitHubGraphQLError(GitHubError):
    """GraphQL returned an ``errors`` array."""
