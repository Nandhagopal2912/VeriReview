"""Command-line interface.

verireview threads OWNER/REPO PR                  list review threads (to pick a comment id)
verireview ingest  OWNER/REPO PR --comment-id ID  build a ReviewCase (JSON) and store it
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from verireview.config import get_settings
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.errors import GitHubError
from verireview.ingestion import ingest_review_case
from verireview.threads import ThreadNotFoundError, reconstruct_threads


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repo = RepoRef(args.repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    settings = get_settings()
    client = GitHubClient(
        settings.github_token,
        api_url=settings.github_api_url,
        timeout_s=settings.github_timeout_s,
        max_retries=settings.github_max_retries,
    )
    if not client.authenticated:
        print(
            "note: no VERIREVIEW_GITHUB_TOKEN; public REST data only, resolution state unknown",
            file=sys.stderr,
        )

    try:
        with client:
            api = GitHubApi(client)
            if args.command == "threads":
                return _threads(api, repo, args.pr)
            return _ingest(api, repo, args.pr, args.comment_id, args.out, args.no_db)
    except (GitHubError, ThreadNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _threads(api: GitHubApi, repo: RepoRef, pr: int) -> int:
    states = api.list_thread_states(repo, pr) if api.can_read_thread_state else None
    threads = reconstruct_threads(api.list_review_comments(repo, pr), states)
    status = {True: "resolved", False: "open", None: "unknown"}
    for t in threads:
        first_line = t.root.body.strip().splitlines()[0][:70] if t.root.body.strip() else ""
        print(
            f"{t.root_comment_id}\t{status[t.is_resolved]:8}\t{len(t.comments)} msg\t"
            f"{t.path}:{t.original_line}\t{first_line}"
        )
    if not threads:
        print("no review threads", file=sys.stderr)
    return 0


def _ingest(
    api: GitHubApi, repo: RepoRef, pr: int, comment_id: int, out: Path | None, no_db: bool
) -> int:
    case = ingest_review_case(api, repo, pr, comment_id)
    payload = case.model_dump_json(indent=2)
    if out is None:
        print(payload)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out}", file=sys.stderr)

    if not no_db:
        # Imported lazily so `--no-db` works without a database driver connection.
        from verireview.db.session import get_sessionmaker
        from verireview.ingestion.store import save_review_case

        with get_sessionmaker()() as session:
            save_review_case(session, case)
        print(f"stored {case.case_id}", file=sys.stderr)

    print(
        f"{case.case_id}: {len(case.window.subsequent_commits)} subsequent commit(s), "
        f"flags={[f.value for f in case.window.flags]}",
        file=sys.stderr,
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verireview")
    sub = parser.add_subparsers(dest="command", required=True)

    threads = sub.add_parser("threads", help="list review threads of a pull request")
    threads.add_argument("repo", help="OWNER/REPO")
    threads.add_argument("pr", type=int)

    ingest = sub.add_parser("ingest", help="reconstruct one review thread as a ReviewCase")
    ingest.add_argument("repo", help="OWNER/REPO")
    ingest.add_argument("pr", type=int)
    ingest.add_argument("--comment-id", type=int, required=True, help="any comment in the thread")
    ingest.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    ingest.add_argument("--no-db", action="store_true", help="do not store in PostgreSQL")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
