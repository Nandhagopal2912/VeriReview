"""Dashboard sign-in and page protection without a database (Phase 13)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from verireview.config import get_settings
from verireview.dashboard import auth
from verireview.dashboard.present import diff_lines, excerpt
from verireview.dashboard.routes import SECURITY_HEADERS
from verireview.main import create_app

TOKEN = "operator-token-for-tests"  # noqa: S105 - test value
PAGES = ["/dashboard", "/dashboard/jobs", "/dashboard/audit/1", "/dashboard/r/1/acme/shop"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("VERIREVIEW_DASHBOARD_TOKEN", TOKEN)
    get_settings.cache_clear()
    auth.limiter.reset()
    yield TestClient(create_app(), follow_redirects=False)
    get_settings.cache_clear()
    auth.limiter.reset()


# ---------------------------------------------------------------- sessions


def test_session_round_trip_and_expiry() -> None:
    token = SecretStr(TOKEN)
    value = auth.issue_session(token, hours=1, now=1_000.0)

    assert auth.session_valid(token, value, now=1_000.0 + 3599)
    assert not auth.session_valid(token, value, now=1_000.0 + 3601)


def test_tampered_or_foreign_sessions_are_rejected() -> None:
    token = SecretStr(TOKEN)
    value = auth.issue_session(token, hours=1, now=1_000.0)
    expires, _, mac = value.partition(".")

    assert not auth.session_valid(token, f"{int(expires) + 99999}.{mac}", now=1_000.0)
    assert not auth.session_valid(SecretStr("rotated-token"), value, now=1_000.0)
    for junk in (None, "", "abc", "12.", ".abc", "x.y"):
        assert not auth.session_valid(token, junk, now=1_000.0)


def test_cookie_value_never_contains_the_token() -> None:
    assert TOKEN not in auth.issue_session(SecretStr(TOKEN), hours=8)


def test_limiter_blocks_after_ten_failures_in_the_window() -> None:
    limiter = auth.LoginLimiter()
    for i in range(10):
        limiter.fail("1.2.3.4", now=100.0 + i)

    assert limiter.blocked("1.2.3.4", now=110.0)
    assert not limiter.blocked("5.6.7.8", now=110.0)
    assert not limiter.blocked("1.2.3.4", now=100.0 + auth.FAILURE_WINDOW_S + 10)


# ---------------------------------------------------------------- routes


def test_dashboard_does_not_exist_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERIREVIEW_DASHBOARD_TOKEN", raising=False)
    monkeypatch.setenv("VERIREVIEW_DASHBOARD_TOKEN", "")
    get_settings.cache_clear()
    anonymous = TestClient(create_app(), follow_redirects=False)

    for url in [*PAGES, "/dashboard/login"]:
        assert anonymous.get(url).status_code == 404
    assert anonymous.post("/dashboard/login", data={"token": ""}).status_code == 404
    get_settings.cache_clear()


def test_pages_redirect_to_sign_in_without_a_session(client: TestClient) -> None:
    for url in PAGES:
        response = client.get(url)
        assert (response.status_code, response.headers["location"]) == (303, "/dashboard/login")


def test_wrong_token_is_refused_without_a_cookie(client: TestClient) -> None:
    response = client.post("/dashboard/login", data={"token": "guess"})

    assert response.status_code == 401
    assert auth.COOKIE not in response.cookies


def test_right_token_sets_a_strict_http_only_cookie(client: TestClient) -> None:
    response = client.post("/dashboard/login", data={"token": TOKEN})

    assert (response.status_code, response.headers["location"]) == (303, "/dashboard")
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/dashboard" in cookie
    assert TOKEN not in cookie


def test_repeated_failures_are_rate_limited(client: TestClient) -> None:
    for _ in range(auth.MAX_FAILURES):
        assert client.post("/dashboard/login", data={"token": "guess"}).status_code == 401

    blocked = client.post("/dashboard/login", data={"token": TOKEN})
    assert blocked.status_code == 429  # even the right token, until the window passes


def test_security_headers_on_every_dashboard_response(client: TestClient) -> None:
    for response in (
        client.get("/dashboard/login"),
        client.get("/dashboard"),
        client.post("/dashboard/login", data={"token": "guess"}),
        client.get("/dashboard/static/style.css"),
    ):
        for header, value in SECURITY_HEADERS.items():
            assert response.headers[header] == value
    assert "script-src" not in SECURITY_HEADERS["Content-Security-Policy"]  # default-src 'none'


def test_stylesheet_is_served_as_css(client: TestClient) -> None:
    response = client.get("/dashboard/static/style.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert "--bg" in response.text


def test_sign_out_clears_the_cookie(client: TestClient) -> None:
    response = client.post("/dashboard/logout")

    assert response.status_code == 303
    assert 'verireview_dashboard=""' in response.headers["set-cookie"]


# ---------------------------------------------------------------- presentation helpers


def test_excerpt_marks_lines_and_stays_in_bounds() -> None:
    code = "\n".join(f"line {i}" for i in range(1, 31))
    lines = excerpt(code, 3, {3})

    assert lines[0].number == 1 and lines[-1].number == 11
    assert [line.number for line in lines if line.marked] == [3]


def test_diff_lines_are_classified_and_capped() -> None:
    lines, truncated = diff_lines("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n same")

    assert [d.kind for d in lines] == ["meta", "meta", "hunk", "del", "add", "ctx"]
    assert not truncated
    assert diff_lines("+x\n" * 500)[1] is True
