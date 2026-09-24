"""GitHub App authentication: JWT, least-privilege per-repository tokens, caching, no leaks."""

import json
import logging

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from pydantic import SecretStr

from helpers.github import FakeGitHubApp, rsa_private_key_pem
from verireview.advisory import INSTALLATION_PERMISSIONS, AppAuthError, GitHubAppAuth
from verireview.gh.api import RepoRef

PEM = rsa_private_key_pem()
NOW = 1_800_000_000.0


def auth(fake: FakeGitHubApp, clock: float = NOW) -> GitHubAppAuth:
    return GitHubAppAuth(1234, SecretStr(PEM), transport=fake.transport, clock=lambda: clock)


def public_key() -> bytes:
    private = serialization.load_pem_private_key(PEM.encode(), password=None)
    return private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def test_app_jwt_is_rs256_signed_short_lived_and_names_the_app() -> None:
    token = auth(FakeGitHubApp()).app_jwt().get_secret_value()
    claims = jwt.decode(
        token,
        public_key(),
        algorithms=["RS256"],
        options={"verify_exp": False, "verify_iat": False},
    )

    assert claims["iss"] == "1234"
    assert claims["exp"] - claims["iat"] <= 600  # GitHub's maximum
    assert claims["iat"] < NOW  # backdated for clock skew


def test_installation_token_is_scoped_to_one_repository_and_least_privilege() -> None:
    fake = FakeGitHubApp()
    token = auth(fake).installation_token(4242, RepoRef("acme/shop"))

    assert token.get_secret_value() == FakeGitHubApp.TOKEN
    assert fake.token_requests == [
        {"repositories": ["shop"], "permissions": INSTALLATION_PERMISSIONS}
    ]
    assert INSTALLATION_PERMISSIONS == {
        "contents": "read",
        "pull_requests": "read",
        "checks": "write",
    }
    [request] = fake.requests
    assert request.url.path == "/app/installations/4242/access_tokens"
    assert request.headers["authorization"].startswith("Bearer ey")  # the App JWT, not a PAT


def test_token_is_reused_until_close_to_expiry_and_per_repository() -> None:
    fake = FakeGitHubApp()
    app = auth(fake)
    app.installation_token(4242, RepoRef("acme/shop"))
    app.installation_token(4242, RepoRef("acme/shop"))
    assert len(fake.token_requests) == 1

    app.installation_token(4242, RepoRef("acme/other"))
    assert len(fake.token_requests) == 2  # another repository never reuses the token


def test_expired_token_is_refreshed() -> None:
    fake = FakeGitHubApp()
    late = auth(fake, clock=4_070_908_700.0)  # 2099-01-01 minus ~2 min: inside the margin
    late.installation_token(4242, RepoRef("acme/shop"))
    late.installation_token(4242, RepoRef("acme/shop"))

    assert len(fake.token_requests) == 2


def test_bad_private_key_fails_without_echoing_it() -> None:
    bogus = "-----BEGIN PRIVATE KEY-----\nnot-a-key\n-----END PRIVATE KEY-----"
    app = GitHubAppAuth(1, SecretStr(bogus), transport=FakeGitHubApp().transport)

    with pytest.raises(AppAuthError) as info:
        app.app_jwt()
    assert "not-a-key" not in str(info.value)


def test_no_key_or_token_reaches_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    fake = FakeGitHubApp()
    app = auth(fake)
    app.installation_token(4242, RepoRef("acme/shop"))
    with app.client_for(4242, RepoRef("acme/shop")) as client:
        client.get_json("/repos/acme/shop/pulls/7")

    logged = caplog.text + json.dumps([r.getMessage() for r in caplog.records])
    assert FakeGitHubApp.TOKEN not in logged
    assert "PRIVATE KEY" not in logged
    assert app.app_jwt().get_secret_value() not in logged
