"""Advisory-mode commands (Phase 11).

verireview worker [--once]
    Process queued advisory jobs (needs the GitHub App settings and the database).
verireview replay-webhook PAYLOAD.json --event EVENT [--delivery ID] [--url URL]
    Sign a recorded webhook payload with the configured secret and POST it to a *local*
    VeriReview server: the offline end-to-end check (docs/phase11_github_advisory.md).
"""

import argparse
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

from verireview.config import get_settings

COMMANDS = ("worker", "replay-webhook")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def add_parsers(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("worker", help="process queued advisory jobs (GitHub App mode)")
    p.add_argument("--once", action="store_true", help="process at most one job, then exit")

    p = sub.add_parser("replay-webhook", help="sign a recorded payload and POST it locally")
    p.add_argument("payload", type=Path)
    p.add_argument("--event", required=True, help="X-GitHub-Event, e.g. pull_request_review_thread")
    p.add_argument("--delivery", help="X-GitHub-Delivery (default: a new UUID)")
    p.add_argument("--url", default="http://localhost:8000/github/webhook")


def run(args: argparse.Namespace) -> int:
    if args.command == "worker":
        return _worker(args.once)
    return _replay(args.payload, args.event, args.delivery or str(uuid.uuid4()), args.url)


def _worker(once: bool) -> int:
    from verireview.advisory.auth import GitHubAppAuth
    from verireview.advisory.worker import AdvisoryWorker
    from verireview.db.session import get_sessionmaker
    from verireview.policy import configured_policy

    settings = get_settings()
    key = settings.app_private_key()
    if settings.github_app_id is None or key is None:
        print(
            "error: set VERIREVIEW_GITHUB_APP_ID and VERIREVIEW_GITHUB_APP_PRIVATE_KEY_PATH "
            "(see docs/phase11_github_advisory.md)",
            file=sys.stderr,
        )
        return 2
    worker = AdvisoryWorker(
        auth=GitHubAppAuth(
            settings.github_app_id,
            key,
            api_url=settings.github_api_url,
            timeout_s=settings.github_timeout_s,
        ),
        sessions=get_sessionmaker(),
        policy=configured_policy(),
        check_name=settings.advisory_check_name,
        max_attempts=settings.worker_max_attempts,
    )
    if once:
        worker.run_once()
        return 0
    worker.run_forever(settings.worker_poll_interval_s)
    return 0  # pragma: no cover - run_forever only returns by exception


def _replay(payload: Path, event: str, delivery: str, url: str) -> int:
    import httpx2 as httpx

    from verireview.advisory.webhooks import sign

    if urlparse(url).hostname not in LOCAL_HOSTS:
        print("error: replay-webhook only posts to a local server", file=sys.stderr)
        return 2
    secret = get_settings().github_webhook_secret
    if secret is None:
        print("error: set VERIREVIEW_GITHUB_WEBHOOK_SECRET", file=sys.stderr)
        return 2
    body = payload.read_bytes()
    response = httpx.post(
        url,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "X-Hub-Signature-256": sign(secret.get_secret_value(), body),
        },
        timeout=30,
    )
    print(f"{response.status_code} {response.text}")
    return 0 if response.status_code < 400 else 1
