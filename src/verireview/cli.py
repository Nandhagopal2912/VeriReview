"""Command-line interface.

GitHub (network):
    verireview threads OWNER/REPO PR                  list review threads (to pick a comment id)
    verireview ingest  OWNER/REPO PR --comment-id ID  build a ReviewCase (JSON) and store it

Local verification (no network):
    verireview verify-fixture DIR                     verify one dev fixture
    verireview verify-case CASE.json                  verify an ingested ReviewCase
    verireview eval-fixtures [--root DIR] [--out F]   evaluate the pipeline on all fixtures

    All three accept --pipeline NAME (default: the latest phase).
"""

import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from verireview.config import get_settings
from verireview.contracts import ReviewCase, VerificationResult
from verireview.dataset import FixtureError, iter_fixtures, load_fixture
from verireview.evaluation import evaluate
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.errors import GitHubError
from verireview.ingestion import ingest_review_case
from verireview.threads import ThreadNotFoundError, reconstruct_threads
from verireview.verification import DEFAULT_PIPELINE, PIPELINES, get_pipeline

DEFAULT_FIXTURES = Path("dataset/fixtures")


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_output()
    args = _parser().parse_args(argv)
    try:
        if args.command in ("threads", "ingest"):
            return _github_command(args)
        if args.command == "verify-fixture":
            fixture = load_fixture(args.directory)
            result = get_pipeline(args.pipeline).run(fixture.case)
            _print_result(result, args.json)
            print(f"expected: {fixture.meta.expected_verdict.value}", file=sys.stderr)
            return 0
        if args.command == "verify-case":
            case = ReviewCase.model_validate_json(args.file.read_text(encoding="utf-8"))
            _print_result(get_pipeline(args.pipeline).run(case), args.json)
            return 0
        return _eval_fixtures(args.root, args.out, args.pipeline)
    except (FixtureError, ValidationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _github_command(args: argparse.Namespace) -> int:
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


def _print_result(result: VerificationResult, as_json: bool) -> None:
    print(result.model_dump_json(indent=2) if as_json else result.explanation)


def _eval_fixtures(root: Path, out: Path | None, pipeline: str) -> int:
    fixtures = list(iter_fixtures(root))
    if not fixtures:
        print(f"error: no fixtures under {root}", file=sys.stderr)
        return 1
    report = evaluate(get_pipeline(pipeline), fixtures, root)
    m = report.metrics
    print(f"pipeline {report.pipeline_version}  dataset {report.dataset_hash[:12]}  n={m.n}")
    print(f"accuracy {m.accuracy:.3f}   macro-F1 {m.macro_f1:.3f}")
    print(
        f"false acceptance {_rate(m.false_acceptance_rate)}   "
        f"false blocking {_rate(m.false_blocking_rate)}"
    )
    print("\nper class           precision  recall   f1    support")
    for verdict, cm in m.per_class.items():
        print(f"  {verdict.value:20}{cm.precision:8.2f}{cm.recall:8.2f}{cm.f1:7.2f}{cm.support:8}")
    print("\nconfusion (rows = expected, cols = predicted: S / P / N / U)")
    for gold, row in m.confusion.items():
        print(f"  {gold.value:20}" + "".join(f"{count:5}" for count in row.values()))
    print("\naccuracy by category:  " + _fmt(report.accuracy_by_category))
    print("accuracy by hard case: " + _fmt(report.accuracy_by_hard_case))
    wrong = [c for c in report.cases if not c.correct]
    if wrong:
        print(f"\nmisclassified ({len(wrong)}):")
        for c in wrong:
            print(f"  {c.case_id:45} expected {c.expected.value:20} got {c.predicted.value}")
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nwrote {out}", file=sys.stderr)
    return 0


def _rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _fmt(values: dict[str, float]) -> str:
    return ", ".join(f"{k} {v:.2f}" for k, v in values.items())


def _utf8_output() -> None:
    """Review comments contain arbitrary Unicode; a Windows console defaults to cp1252."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


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

    verify_fixture = sub.add_parser("verify-fixture", help="verify one dev fixture directory")
    verify_fixture.add_argument("directory", type=Path)
    verify_fixture.add_argument("--json", action="store_true", help="print the full result")

    verify_case = sub.add_parser("verify-case", help="verify an ingested ReviewCase JSON file")
    verify_case.add_argument("file", type=Path)
    verify_case.add_argument("--json", action="store_true", help="print the full result")

    eval_fixtures = sub.add_parser("eval-fixtures", help="evaluate the pipeline on all fixtures")
    eval_fixtures.add_argument("--root", type=Path, default=DEFAULT_FIXTURES)
    eval_fixtures.add_argument("--out", type=Path, help="write the JSON report here")

    for command in (verify_fixture, verify_case, eval_fixtures):
        command.add_argument(
            "--pipeline",
            choices=sorted(PIPELINES),
            default=DEFAULT_PIPELINE,
            help=f"verification pipeline (default: {DEFAULT_PIPELINE})",
        )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
