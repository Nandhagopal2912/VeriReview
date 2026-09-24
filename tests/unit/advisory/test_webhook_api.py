"""POST /github/webhook without a database: signature first, then parsing, then queueing."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from helpers.github import load_webhook
from verireview.advisory import sign
from verireview.api import webhooks
from verireview.config import get_settings
from verireview.db.session import get_session
from verireview.main import create_app

SECRET = "s3cret-for-tests"  # noqa: S105 - test value


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.seen: set[str] = set()

    def enqueue(self, _session: object, delivery: str, event: str, tasks: list) -> int:  # type: ignore[type-arg]
        self.calls.append((delivery, event, len(tasks)))
        if delivery in self.seen:
            return 0
        self.seen.add(delivery)
        return len(tasks)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Iterator[Recorder]:
    monkeypatch.setenv("VERIREVIEW_GITHUB_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    rec = Recorder()
    monkeypatch.setattr(webhooks, "enqueue", rec.enqueue)
    yield rec
    get_settings.cache_clear()


@pytest.fixture
def client(recorder: Recorder) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: None
    return TestClient(app)


def post(
    client: TestClient,
    name: str,
    event: str,
    delivery: str = "d-1",
    signature: str | None = "auto",
    body: bytes | None = None,
) -> tuple[int, dict]:  # type: ignore[type-arg]
    data = body if body is not None else load_webhook(name)
    headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": delivery}
    if signature == "auto":
        headers["X-Hub-Signature-256"] = sign(SECRET, data)
    elif signature is not None:
        headers["X-Hub-Signature-256"] = signature
    response = client.post("/github/webhook", content=data, headers=headers)
    return response.status_code, response.json()


def test_signed_resolved_thread_is_queued(client: TestClient, recorder: Recorder) -> None:
    code, body = post(client, "thread_resolved.json", "pull_request_review_thread")

    assert (code, body) == (202, {"status": "queued", "jobs": 1})
    assert recorder.calls == [("d-1", "pull_request_review_thread", 1)]


def test_redelivery_is_processed_once(client: TestClient, recorder: Recorder) -> None:
    post(client, "thread_resolved.json", "pull_request_review_thread")
    code, body = post(client, "thread_resolved.json", "pull_request_review_thread")

    assert (code, body) == (202, {"status": "duplicate", "jobs": 0})


@pytest.mark.parametrize("signature", [None, "sha256=" + "0" * 64, "sha1=abc"])
def test_forged_delivery_is_rejected_before_parsing(
    client: TestClient, recorder: Recorder, signature: str | None
) -> None:
    code, _ = post(
        client, "thread_resolved.json", "pull_request_review_thread", signature=signature
    )

    assert code == 401
    assert recorder.calls == []


def test_signature_is_checked_before_json_is_parsed(client: TestClient, recorder: Recorder) -> None:
    code, _ = post(client, "", "pull_request_review_thread", body=b"{not json", signature=None)

    assert code == 401  # not 400: an unsigned body is never read


def test_signed_but_malformed_payload_is_a_bad_request(client: TestClient) -> None:
    code, _ = post(client, "", "pull_request_review_thread", body=b"{not json")

    assert code == 400


def test_ping_and_irrelevant_events(client: TestClient, recorder: Recorder) -> None:
    assert post(client, "ping.json", "ping")[1]["status"] == "pong"
    assert post(client, "thread_unresolved.json", "pull_request_review_thread", "d-2")[1] == {
        "status": "ignored",
        "jobs": 0,
    }
    assert recorder.calls == []


def test_malformed_headers_are_rejected(client: TestClient) -> None:
    code, _ = post(client, "ping.json", "ping", delivery="../../etc")

    assert code == 400


def test_oversized_body_is_rejected(client: TestClient) -> None:
    code, _ = post(client, "", "ping", body=b"x" * (webhooks.MAX_BODY_BYTES + 1))

    assert code == 413


def test_without_a_secret_nothing_is_accepted(
    monkeypatch: pytest.MonkeyPatch, recorder: Recorder
) -> None:
    monkeypatch.delenv("VERIREVIEW_GITHUB_WEBHOOK_SECRET")
    monkeypatch.setenv("VERIREVIEW_GITHUB_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: None

    code, _ = post(TestClient(app), "thread_resolved.json", "pull_request_review_thread")

    assert code == 503
    assert recorder.calls == []
