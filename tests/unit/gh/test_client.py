from collections.abc import Callable

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from verireview.gh.client import GitHubClient
from verireview.gh.errors import (
    GitHubAuthRequiredError,
    GitHubGraphQLError,
    GitHubNotFoundError,
    GitHubRateLimitedError,
    GitHubRequestError,
)

TOKEN = SecretStr("ghp_supersecret")


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    token: SecretStr | None = TOKEN,
    sleeps: list[float] | None = None,
) -> GitHubClient:
    recorded = sleeps if sleeps is not None else []
    return GitHubClient(
        token,
        transport=httpx.MockTransport(handler),
        max_retries=2,
        sleep=recorded.append,
    )


def test_sends_token_and_api_version_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    make_client(handler).get_json("/repos/a/b")

    assert seen[0].headers["authorization"] == "Bearer ghp_supersecret"
    assert seen[0].headers["x-github-api-version"] == "2022-11-28"


def test_no_authorization_header_without_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    client = make_client(handler, token=None)
    client.get_json("/repos/a/b")

    assert "authorization" not in seen[0].headers
    assert client.authenticated is False


def test_follows_link_header_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[3])
        next_url = "https://api.github.com/repositories/1/pulls/1/comments?per_page=100&page=2"
        return httpx.Response(200, json=[1, 2], headers={"link": f'<{next_url}>; rel="next"'})

    assert make_client(handler).get_paginated("/repos/a/b/pulls/1/comments") == [1, 2, 3]


def test_pagination_respects_max_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=list(range(100)), headers={"link": '</repos/a/b/x?page=2>; rel="next"'}
        )

    assert len(make_client(handler).get_paginated("/repos/a/b/x", max_items=150)) == 150


def test_404_raises_not_found() -> None:
    client = make_client(lambda _: httpx.Response(404, json={"message": "Not Found"}))

    with pytest.raises(GitHubNotFoundError):
        client.get_json("/repos/a/b")


def test_retries_server_errors_with_backoff_then_succeeds() -> None:
    responses = iter([httpx.Response(502), httpx.Response(503), httpx.Response(200, json=[])])
    sleeps: list[float] = []

    result = make_client(lambda _: next(responses), sleeps=sleeps).get_json("/repos/a/b")

    assert result == []
    assert sleeps == [1.0, 2.0]


def test_gives_up_after_max_retries() -> None:
    with pytest.raises(GitHubRequestError) as exc_info:
        make_client(lambda _: httpx.Response(500)).get_json("/repos/a/b")

    assert exc_info.value.status_code == 500


def test_client_errors_are_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(422)

    with pytest.raises(GitHubRequestError):
        make_client(handler).get_json("/repos/a/b")
    assert len(calls) == 1


def test_short_rate_limit_is_waited_out() -> None:
    responses = iter(
        [
            httpx.Response(403, headers={"retry-after": "5"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    sleeps: list[float] = []

    assert make_client(lambda _: next(responses), sleeps=sleeps).get_json("/x") == {"ok": True}
    assert sleeps == [5.0]


def test_long_rate_limit_fails_fast_with_reset_time() -> None:
    headers = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "4102444800"}  # year 2100
    sleeps: list[float] = []
    client = make_client(lambda _: httpx.Response(403, headers=headers), sleeps=sleeps)

    with pytest.raises(GitHubRateLimitedError) as exc_info:
        client.get_json("/repos/a/b")

    assert exc_info.value.reset_at is not None
    assert exc_info.value.reset_at.year == 2100
    assert sleeps == []


def test_forbidden_without_rate_limit_headers_is_a_plain_error() -> None:
    with pytest.raises(GitHubRequestError) as exc_info:
        make_client(lambda _: httpx.Response(403)).get_json("/repos/a/b")

    assert exc_info.value.status_code == 403


def test_transport_errors_are_retried() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={})

    assert make_client(handler).get_json("/repos/a/b") == {}
    assert len(attempts) == 2


def test_graphql_requires_token() -> None:
    client = make_client(lambda _: httpx.Response(200, json={}), token=None)

    with pytest.raises(GitHubAuthRequiredError):
        client.graphql("query { viewer { login } }", {})


def test_graphql_errors_are_raised() -> None:
    body = {"data": None, "errors": [{"message": "Field 'x' doesn't exist"}]}
    client = make_client(lambda _: httpx.Response(200, json=body))

    with pytest.raises(GitHubGraphQLError, match="Field 'x'"):
        client.graphql("query { x }", {})


def test_get_text_returns_raw_content() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"print('hi')\n")

    assert make_client(handler).get_text("/repos/a/b/contents/x.py") == "print('hi')\n"
    assert seen[0].headers["accept"] == "application/vnd.github.raw+json"


@pytest.mark.parametrize("path", ["https://evil.example/steal", "//evil.example/x", "repos/a/b"])
def test_refuses_paths_that_could_leak_the_token(path: str) -> None:
    client = make_client(lambda _: httpx.Response(200, json={}))

    with pytest.raises(ValueError, match="non-API path"):
        client.get_json(path)


def test_errors_never_contain_the_token() -> None:
    client = make_client(lambda _: httpx.Response(500))

    with pytest.raises(GitHubRequestError) as exc_info:
        client.get_json("/repos/a/b")

    assert "supersecret" not in str(exc_info.value)
