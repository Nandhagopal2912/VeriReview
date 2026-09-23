from collections.abc import Iterator
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from helpers.github import FakeGitHub
from verireview.api.verify import get_github_reader
from verireview.dataset import load_fixture
from verireview.gh.api import GitHubApi, GitHubReader
from verireview.gh.client import GitHubClient
from verireview.verification import MVP_VERSION

FIXTURES = Path(__file__).resolve().parents[3] / "dataset" / "fixtures"


def use_reader(app: FastAPI, transport: httpx.BaseTransport) -> None:
    def reader() -> Iterator[GitHubReader]:
        with GitHubClient(SecretStr("t"), transport=transport, sleep=lambda _: None) as client:
            yield GitHubApi(client)

    app.dependency_overrides[get_github_reader] = reader


def test_verify_a_review_case(client: TestClient) -> None:
    case = load_fixture(FIXTURES / "api-003-wrong-status-code").case

    response = client.post("/verify", json={"case": case.model_dump(mode="json")})

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["verdict"] == "NOT_SATISFIED"
    assert body["result"]["pipeline_version"] == MVP_VERSION
    assert body["policy"]["recommended"] == "BLOCK"
    assert body["policy"]["action"] == "WARN"  # blocking disabled by default
    assert body["policy"]["blocks_merge"] is False


def test_pipeline_can_be_chosen(client: TestClient) -> None:
    case = load_fixture(FIXTURES / "validation-001-none-check").case

    response = client.post(
        "/verify", json={"case": case.model_dump(mode="json"), "pipeline": "phase2-locality"}
    )

    assert response.json()["result"]["pipeline_version"] == "phase2-locality-1"


def test_unknown_pipeline_is_rejected(client: TestClient) -> None:
    case = load_fixture(FIXTURES / "validation-001-none-check").case

    response = client.post("/verify", json={"case": case.model_dump(mode="json"), "pipeline": "x"})

    assert response.status_code == 422


def test_verify_from_github(app: FastAPI, client: TestClient) -> None:
    use_reader(app, FakeGitHub().transport)

    response = client.post(
        "/verify/github", json={"repository": "acme/shop", "pull_number": 7, "comment_id": 5001}
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["case_id"] == "acme/shop#7/5001"
    # "validate username is not empty … and add a unit test": both done in the fixture PR.
    assert result["verdict"] == "SATISFIED"


def test_unknown_comment_is_404(app: FastAPI, client: TestClient) -> None:
    use_reader(app, FakeGitHub().transport)

    response = client.post(
        "/verify/github", json={"repository": "acme/shop", "pull_number": 7, "comment_id": 1}
    )

    assert response.status_code == 404


def test_rate_limit_is_503(app: FastAPI, client: TestClient) -> None:
    limited = httpx.MockTransport(
        lambda _: httpx.Response(
            403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "4102444800"}
        )
    )
    use_reader(app, limited)

    response = client.post(
        "/verify/github", json={"repository": "acme/shop", "pull_number": 7, "comment_id": 5001}
    )

    assert response.status_code == 503


@pytest.mark.parametrize("repository", ["acme", "acme/shop/x", "../etc/passwd"])
def test_bad_repository_is_422(client: TestClient, repository: str) -> None:
    response = client.post(
        "/verify/github", json={"repository": repository, "pull_number": 7, "comment_id": 1}
    )

    assert response.status_code == 422
