"""Advisory-mode commands (Phase 11).

verireview worker [--once]
    Process queued advisory jobs (needs the GitHub App settings and the database).
verireview replay-webhook PAYLOAD.json --event EVENT [--delivery ID] [--url URL]
    Sign a recorded webhook payload with the configured secret and POST it to a *local*
    VeriReview server: the offline end-to-end check (docs/phase11_github_advisory.md).
verireview enforcement-eligibility REPORT.json [--system F] [--write]
    Phase 12: per-category false-acceptance / false-blocking upper bounds from a frozen test
    run; --write replaces the eligibility shipped with the package.
verireview repo-policy show OWNER/REPO --installation ID
verireview repo-policy set OWNER/REPO --installation ID --stage STAGE [--categories a,b]
                       --actor NAME --reason TEXT
    Phase 12: a repository's rollout stage (one step up at a time, rollback any time).
"""

import argparse
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

from verireview.config import get_settings

COMMANDS = ("worker", "replay-webhook", "enforcement-eligibility", "repo-policy")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def add_parsers(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("worker", help="process queued advisory jobs (GitHub App mode)")
    p.add_argument("--once", action="store_true", help="process at most one job, then exit")

    p = sub.add_parser("replay-webhook", help="sign a recorded payload and POST it locally")
    p.add_argument("payload", type=Path)
    p.add_argument("--event", required=True, help="X-GitHub-Event, e.g. pull_request_review_thread")
    p.add_argument("--delivery", help="X-GitHub-Delivery (default: a new UUID)")
    p.add_argument("--url", default="http://localhost:8000/github/webhook")

    p = sub.add_parser(
        "enforcement-eligibility", help="per-category enforcement gate from a frozen test run"
    )
    p.add_argument("report", type=Path, help="eval-benchmark --final-test-run report (JSON)")
    p.add_argument("--system", default="F")
    p.add_argument(
        "--write", action="store_true", help="replace the eligibility shipped with the package"
    )

    p = sub.add_parser("repo-policy", help="show or change a repository's rollout stage")
    p.add_argument("action", choices=["show", "set"])
    p.add_argument("repository", help="OWNER/REPO")
    p.add_argument("--installation", type=int, required=True, help="GitHub App installation id")
    p.add_argument(
        "--stage", choices=["observe", "advisory", "human_review", "enforcement"], help="for set"
    )
    p.add_argument("--categories", default="", help="enforced categories (comma-separated)")
    p.add_argument("--actor", default="", help="who decides (recorded)")
    p.add_argument("--reason", default="", help="why (recorded, at least 10 characters)")


def run(args: argparse.Namespace) -> int:
    if args.command == "worker":
        return _worker(args.once)
    if args.command == "enforcement-eligibility":
        return _eligibility(args.report, args.system, args.write)
    if args.command == "repo-policy":
        return _repo_policy(args)
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


def _eligibility(report: Path, system: str, write: bool) -> int:
    from verireview.enforcement import eligibility

    result = eligibility.compute(report, system)
    print(
        f"{result.system} on {result.source_report} (split {result.split}, manifest "
        f"{result.manifest_version}, protocol {result.protocol_sha256[:12]}); gate: one-sided "
        f"{result.confidence:.0%} upper bounds <= {result.threshold}"
    )
    header = f"{'category':15} {'bad':>4} {'FA':>3} {'FAR up':>7} {'good':>5} {'FB':>3}"
    print(f"{header} {'FBR up':>7}  eligible")
    for c in result.categories:
        print(
            f"{c.category.value:15} {c.bad_cases:4} {c.false_accepts:3} {c.far_upper:7.3f} "
            f"{c.good_cases:5} {c.false_blocks:3} {c.fbr_upper:7.3f}  "
            f"{'yes' if c.eligible else 'no'}"
        )
    eligible = sorted(c.value for c in result.eligible_categories())
    print(f"eligible: {', '.join(eligible) or 'none'}")
    if write:
        target = Path(eligibility.__file__).with_name(eligibility.SHIPPED)
        eligibility.write(result, target)
        print(f"wrote {target}")
    return 0


def _repo_policy(args: argparse.Namespace) -> int:
    from verireview.contracts import RequirementCategory
    from verireview.db.session import get_sessionmaker
    from verireview.enforcement.eligibility import eligible_categories
    from verireview.enforcement.stages import (
        StageChangeError,
        change_stage,
        confirmations_since,
        current,
    )
    from verireview.gh.api import RepoRef
    from verireview.policy import OperatingMode

    repo = RepoRef(args.repository).full_name
    settings = get_settings()
    with get_sessionmaker()() as session:
        if args.action == "set":
            if args.stage is None:
                print("error: --stage is required for set", file=sys.stderr)
                return 2
            try:
                categories = [
                    RequirementCategory(c.strip()) for c in args.categories.split(",") if c.strip()
                ]
                change_stage(
                    session,
                    args.installation,
                    repo,
                    OperatingMode(args.stage),
                    actor=args.actor,
                    reason=args.reason,
                    eligible=eligible_categories(),
                    categories=categories,
                    min_days=settings.enforcement_min_human_review_days,
                    min_confirmations=settings.enforcement_min_confirmations,
                )
            except (StageChangeError, ValueError) as exc:
                print(f"refused: {exc}", file=sys.stderr)
                return 1
        row = current(session, args.installation, repo)
        if row is None:
            print(f"{repo}: no opt-in (runs at the global default, at most human_review)")
            return 0
        confirmed = confirmations_since(session, args.installation, repo, row.stage_since)
        enforced = ", ".join(row.enforced_categories) or "-"
        print(
            f"{repo}: stage {row.stage} since {row.stage_since:%Y-%m-%d} (by {row.updated_by}); "
            f"enforced categories: {enforced}; confirmations since: {confirmed}; global "
            f"blocking switch: {'on' if settings.policy_allow_block else 'off'}"
        )
    return 0
