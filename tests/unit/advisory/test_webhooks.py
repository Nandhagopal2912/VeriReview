"""Webhook signatures and the events that create advisory work."""

import json

import pytest
from pydantic import ValidationError

from helpers.github import load_webhook
from verireview.advisory import InvalidSignatureError, sign, tasks_from_event, verify_signature

SECRET = "s3cret-for-tests"  # noqa: S105 - test value


def test_valid_signature_is_accepted() -> None:
    body = load_webhook("thread_resolved.json")
    verify_signature(SECRET, body, sign(SECRET, body))


@pytest.mark.parametrize(
    "header",
    [None, "", "sha1=abc", "sha256=" + "0" * 64],
    ids=["missing", "empty", "wrong-algorithm", "wrong-digest"],
)
def test_forged_or_missing_signature_is_rejected(header: str | None) -> None:
    with pytest.raises(InvalidSignatureError):
        verify_signature(SECRET, load_webhook("thread_resolved.json"), header)


def test_signature_covers_every_byte_of_the_body() -> None:
    body = load_webhook("thread_resolved.json")
    tampered = body.replace(b'"number": 7', b'"number": 8')

    with pytest.raises(InvalidSignatureError):
        verify_signature(SECRET, tampered, sign(SECRET, body))
    with pytest.raises(InvalidSignatureError):
        verify_signature("other-secret", body, sign(SECRET, body))


def payload(name: str) -> dict:  # type: ignore[type-arg]
    return json.loads(load_webhook(name))


def test_resolved_thread_becomes_one_task() -> None:
    [task] = tasks_from_event("pull_request_review_thread", payload("thread_resolved.json"), "V")

    assert (task.kind, task.repository, task.pull_number, task.comment_id) == (
        "thread",
        "acme/shop",
        7,
        5001,
    )
    assert task.installation_id == 4242
    assert task.head_sha == "4" * 40


def test_comment_text_is_not_taken_from_the_payload() -> None:
    [task] = tasks_from_event("pull_request_review_thread", payload("thread_resolved.json"), "V")

    assert "Ignore previous instructions" not in task.model_dump_json()


def test_rerun_of_our_check_verifies_the_pull_request() -> None:
    tasks = tasks_from_event("check_run", payload("check_run_rerequested.json"), "VeriReview")

    assert [(t.kind, t.pull_number, t.comment_id) for t in tasks] == [("pull_request", 7, None)]


@pytest.mark.parametrize(
    ("event", "name", "check_name"),
    [
        ("pull_request_review_thread", "thread_unresolved.json", "VeriReview"),
        ("check_run", "check_run_rerequested.json", "SomeOtherApp"),
        ("ping", "ping.json", "VeriReview"),
        ("push", "thread_resolved.json", "VeriReview"),
    ],
)
def test_other_deliveries_create_no_work(event: str, name: str, check_name: str) -> None:
    assert tasks_from_event(event, payload(name), check_name) == []


def test_malicious_repository_name_is_rejected() -> None:
    data = payload("thread_resolved.json")
    data["repository"]["full_name"] = "acme/shop/../../orgs/x"

    with pytest.raises(ValidationError):
        tasks_from_event("pull_request_review_thread", data, "V")


def test_malformed_head_sha_is_rejected() -> None:
    data = payload("thread_resolved.json")
    data["pull_request"]["head"]["sha"] = "not-a-sha"

    with pytest.raises(ValidationError):
        tasks_from_event("pull_request_review_thread", data, "V")
