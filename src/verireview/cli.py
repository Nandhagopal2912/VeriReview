"""Command-line interface.

GitHub (network):
    verireview threads OWNER/REPO PR                  list review threads (to pick a comment id)
    verireview ingest  OWNER/REPO PR --comment-id ID  build a ReviewCase (JSON) and store it

Local verification (no network):
    verireview verify-fixture DIR                     verify one dev fixture
    verireview verify-case CASE.json                  verify an ingested ReviewCase
    verireview eval-fixtures [--root DIR] [--out F]   evaluate the pipeline on all fixtures
    verireview extract "COMMENT" [--code FILE]        show extracted requirements
    verireview eval-requirements                      score extraction vs gold (dev + held-out)
    verireview eval-baselines [--scorers …] [--views …]  NLP baselines vs. rules (dev + held-out)
    verireview eval-semantic                          code-model evidence: signal, verdict changes
    verireview eval-injection [--pipeline NAME]       prompt-injection robustness (dev + held-out)

    verify-fixture, verify-case, eval-fixtures and eval-injection accept --pipeline NAME
    (default: mvp).
"""

import argparse
import io
import json
import sys
from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from verireview.api.verify import VerifyResponse
from verireview.config import get_settings
from verireview.contracts import ReviewCase, VerificationResult
from verireview.dataset import FixtureError, iter_fixtures, load_fixture
from verireview.evaluation import Verifier, dataset_hash, evaluate
from verireview.evaluation.requirements import (
    ExtractionReport,
    evaluate_extraction,
    file_hash,
    fixture_examples,
    heldout_examples,
)
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.errors import GitHubError
from verireview.ingestion import ingest_review_case
from verireview.policy import configured_policy, decide
from verireview.requirements import CodeContext, extract_requirements
from verireview.threads import ThreadNotFoundError, reconstruct_threads
from verireview.verification import DEFAULT_PIPELINE, PIPELINES, get_pipeline

if TYPE_CHECKING:
    from verireview.semantic import Scorer, View

DEFAULT_FIXTURES = Path("dataset/fixtures")
DEFAULT_HELDOUT = Path("dataset/requirements/heldout.jsonl")
DEFAULT_HELDOUT_FIXTURES = Path("dataset/heldout_fixtures")


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
        if args.command == "extract":
            code = args.code.read_text(encoding="utf-8") if args.code else None
            extracted = extract_requirements(
                args.comment, context=CodeContext.from_code(code, args.line)
            )
            print(extracted.model_dump_json(indent=2))
            return 0
        if args.command == "eval-requirements":
            return _eval_requirements(args.root, args.heldout, args.out)
        if args.command == "eval-baselines":
            return _eval_baselines(args.root, args.heldout, args.scorers, args.views, args.out)
        if args.command == "eval-semantic":
            return _eval_semantic(args.root, args.heldout, args.out)
        if args.command == "eval-injection":
            return _eval_injection(args)
        return _eval_fixtures(args.root, args.out, args.pipeline, args.gold_requirements)
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
    policy = decide(result, configured_policy())
    if as_json:
        print(VerifyResponse(result=result, policy=policy).model_dump_json(indent=2))
        return
    print(result.explanation)
    print(
        f"\nRecommended action:\n{policy.action.value} ({policy.mode.value} mode). {policy.reason}"
    )


def _eval_fixtures(root: Path, out: Path | None, pipeline: str, gold: bool) -> int:
    fixtures = list(iter_fixtures(root))
    if not fixtures:
        print(f"error: no fixtures under {root}", file=sys.stderr)
        return 1
    report = evaluate(get_pipeline(pipeline), fixtures, root, gold_requirements=gold)
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
    for expected, row in m.confusion.items():
        print(f"  {expected.value:20}" + "".join(f"{count:5}" for count in row.values()))
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


def _eval_requirements(root: Path, heldout: Path, out: Path | None) -> int:
    reports = [
        evaluate_extraction(
            fixture_examples(list(iter_fixtures(root))), "dev fixtures", dataset_hash(root)
        ),
        evaluate_extraction(heldout_examples(heldout), "held-out", file_hash(heldout)),
    ]
    for report in reports:
        _print_extraction(report)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = "[" + ",\n".join(r.model_dump_json(indent=2) for r in reports) + "]\n"
        out.write_text(payload, encoding="utf-8", newline="\n")
        print(f"wrote {out}", file=sys.stderr)
    return 0


def _scorers() -> "dict[str, Callable[[], Scorer]]":
    from verireview.semantic import CodeModelScorer, EmbeddingScorer, LexicalScorer, TfidfScorer

    return {
        "lexical": LexicalScorer,
        "tfidf": TfidfScorer,
        "embedding": EmbeddingScorer,
        "unixcoder": CodeModelScorer,
    }


def _choices(value: str, available: Collection[str], what: str) -> list[str] | None:
    names = [s.strip() for s in value.split(",") if s.strip()]
    unknown = [n for n in names if n not in available]
    if unknown:
        print(
            f"error: unknown {what}(s) {unknown}; choose from {sorted(available)}", file=sys.stderr
        )
        return None
    return names


def _eval_baselines(root: Path, heldout: Path, scorers: str, views: str, out: Path | None) -> int:
    # Imported here: the embedding and code-model scorers need the optional `nlp` group.
    from verireview.evaluation.baselines import BaselineReport, current_commit, run_baseline
    from verireview.semantic import VIEWS

    available = _scorers()
    names = _choices(scorers, available, "scorer")
    chosen_views = _choices(views, VIEWS, "view")
    if names is None or chosen_views is None:
        return 2
    dev, held = list(iter_fixtures(root)), list(iter_fixtures(heldout))
    results = [
        run_baseline(available[n](), dev, held, root, heldout, cast("View", v))
        for n in names
        for v in chosen_views
    ]
    rules = [
        evaluate(get_pipeline(DEFAULT_PIPELINE), fx, r) for fx, r in ((dev, root), (held, heldout))
    ]

    print(f"{'verifier':34}{'set':10}{'acc':>7}{'mF1':>7}{'FAR':>7}{'FBR':>7}  threshold")
    rows = []
    for r in results:
        label = _baseline_label(r.scorer, r.view)
        rows.append((f"{label} [accuracy-tuned]", r.dev, r.heldout, f"{r.threshold:.3f}"))
        rows.append(
            (f"{label} [Youden]", r.dev_youden, r.heldout_youden, f"{r.youden_threshold:.3f}")
        )
    rows.append((f"rules ({DEFAULT_PIPELINE})", rules[0], rules[1], "-"))
    for name, dev_report, held_report, threshold in rows:
        for label, evaluation in (("dev", dev_report), ("held-out", held_report)):
            m = evaluation.metrics
            far, fbr = _rate(m.false_acceptance_rate), _rate(m.false_blocking_rate)
            scores = f"{m.accuracy:7.3f}{m.macro_f1:7.3f}{far:>7}{fbr:>7}"
            print(f"{name:34}{label:10}{scores}  {threshold}")
    print("\nROC-AUC, valid vs invalid resolution (0.5 = no signal):")
    for r in results:
        label = _baseline_label(r.scorer, r.view)
        print(f"  {label:16} dev {_rate(r.auc_dev)}   held-out {_rate(r.auc_heldout)}")
    if out is not None:
        payload = BaselineReport(commit=current_commit(), results=results)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nwrote {out}", file=sys.stderr)
    return 0


def _baseline_label(scorer: str, view: str) -> str:
    return scorer if view == "added" else f"{scorer}/{view}"


def _eval_semantic(root: Path, heldout: Path, out: Path | None) -> int:
    from verireview.evaluation.baselines import current_commit
    from verireview.evaluation.semantic import (
        evaluate_semantic_evidence,
        operating_point,
        youden_threshold,
    )
    from verireview.semantic import default_code_encoder

    encoder = default_code_encoder()
    reports = [
        evaluate_semantic_evidence(name, list(iter_fixtures(r)), r, encoder)
        for name, r in (("dev fixtures", root), ("held-out", heldout))
    ]
    threshold = youden_threshold(reports[0])  # dev only; held-out uses it unchanged
    for report in reports:
        far, fbr = operating_point(report, threshold)
        print(f"\n== {report.name}  (n={report.n}, dataset {report.dataset_hash[:12]})")
        print(f"verdict changes vs mvp        {report.verdict_changes}")
        print(f"ROC-AUC valid vs invalid      {_rate(report.auc)}  (weakest requirement)")
        print(
            f"if relevance >= {threshold:.3f} meant SATISFIED (dev Youden): "
            f"false acceptance {_rate(far)}, false blocking {_rate(fbr)}"
        )
        print(f"  {'case':42}{'gold':22}{'mvp':22}relevance")
        for c in report.cases:
            mark = "" if c.mvp == c.gold else "   <- rules wrong or undecided"
            print(f"  {c.case_id:42}{c.gold.value:22}{c.mvp.value:22}{c.case_score:.2f}{mark}")
    model = reports[-1].model  # recorded after both sets, so truncation counts are complete
    print(f"\nmodel: {model}")
    if out is not None:
        payload = {
            "commit": current_commit(),
            "model": model,
            "youden_threshold": threshold,
            "reports": [r.model_dump(mode="json") for r in reports],
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out}", file=sys.stderr)
    return 0


def _eval_injection(args: argparse.Namespace) -> int:
    from verireview.evaluation.baselines import current_commit
    from verireview.evaluation.injection import INJECTIONS, Site, injection_report
    from verireview.semantic import SimilarityVerifier, comment_text

    dev, held = list(iter_fixtures(args.root)), list(iter_fixtures(args.heldout))
    verifier: Verifier
    if args.baseline:
        available = _scorers()
        if args.baseline not in available or args.threshold is None:
            print(
                f"error: --baseline needs one of {sorted(available)} and --threshold",
                file=sys.stderr,
            )
            return 2
        baseline = SimilarityVerifier(available[args.baseline](), args.threshold, args.view)
        corpus = [comment_text(f.case) for f in dev] + [baseline.change(f.case) for f in dev]
        baseline.scorer.fit(corpus)  # dev only, as in Phase 6
        verifier = baseline
    else:
        verifier = get_pipeline(args.pipeline)
    reports = [injection_report(verifier, fx) for fx in (dev, held)]

    print(f"verifier: {verifier.version}; {len(INJECTIONS)} injected texts per site")
    print(f"{'site':22}{'dev':>14}{'held-out':>14}   (outcome changes / variants)")
    for site in Site:
        cells = []
        for report in reports:
            changed = sum(f.site == site for f in report.flips)
            cells.append(f"{changed}/{report.by_site[site]}")
        print(f"{site.value:22}{cells[0]:>14}{cells[1]:>14}")
    total = [f"{len(r.flips)}/{r.variants}" for r in reports]
    print(f"{'total':22}{total[0]:>14}{total[1]:>14}")
    for report, name in zip(reports, ("dev", "held-out"), strict=True):
        for flip in report.flips:
            print(
                f"  changed ({name}): {flip.case_id} {flip.site.value} #{flip.injection}: "
                f"{flip.expected.verdict.value} -> {flip.actual.verdict.value}"
            )
    if args.out is not None:
        payload = {
            "commit": current_commit(),
            "injections": list(INJECTIONS),
            "reports": [r.model_dump(mode="json") for r in reports],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


def _print_extraction(report: ExtractionReport) -> None:
    print(f"\n== {report.name}  (n={report.n}, dataset {report.dataset_hash[:12]})")
    print(f"requirement count exact  {report.count_exact:.3f}")
    print(
        f"category P/R/F1          {report.category_precision:.3f} / "
        f"{report.category_recall:.3f} / {report.category_f1:.3f}"
    )
    print(f"actionable accuracy      {report.actionable_accuracy:.3f}")
    print(
        f"ambiguity P/R            {_rate(report.ambiguity_precision)} / "
        f"{_rate(report.ambiguity_recall)}"
    )
    print(f"target symbol accuracy   {_rate(report.target_symbol_accuracy)}")
    wrong = [
        e
        for e in report.examples
        if e.gold_count != e.predicted_count
        or sorted(e.gold_categories) != sorted(e.predicted_categories)
        or (e.gold_ambiguous is not None and e.gold_ambiguous != e.predicted_ambiguous)
    ]
    for e in wrong:
        print(
            f"  {e.id:42} gold {e.gold_categories} amb={e.gold_ambiguous}  "
            f"got {e.predicted_categories} amb={e.predicted_ambiguity}"
        )


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
    eval_fixtures.add_argument(
        "--gold-requirements",
        action="store_true",
        help="use annotated requirements instead of extraction (isolates rule errors)",
    )

    extract = sub.add_parser("extract", help="extract structured requirements from a comment")
    extract.add_argument("comment")
    extract.add_argument("--code", type=Path, help="the commented file (for targets)")
    extract.add_argument("--line", type=int, help="commented line in --code")

    eval_req = sub.add_parser("eval-requirements", help="score requirement extraction")
    eval_req.add_argument("--root", type=Path, default=DEFAULT_FIXTURES)
    eval_req.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT)
    eval_req.add_argument("--out", type=Path, help="write the JSON reports here")

    eval_base = sub.add_parser(
        "eval-baselines", help="Phase 6 NLP baselines vs. the rules, on dev and held-out"
    )
    eval_base.add_argument("--root", type=Path, default=DEFAULT_FIXTURES)
    eval_base.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT_FIXTURES)
    eval_base.add_argument(
        "--scorers",
        default="lexical,tfidf,embedding",
        help="comma-separated: lexical, tfidf, embedding, unixcoder "
        "(embedding and unixcoder need `uv sync --group nlp`)",
    )
    eval_base.add_argument(
        "--views",
        default="added",
        help="comma-separated views of the change: added (all added lines, Phase 6), "
        "code (comments and docstrings removed, Phase 7)",
    )
    eval_base.add_argument("--out", type=Path, help="write the JSON report here")

    eval_sem = sub.add_parser(
        "eval-semantic", help="Phase 7 code-model evidence (needs the nlp group): signal, verdicts"
    )
    eval_sem.add_argument("--root", type=Path, default=DEFAULT_FIXTURES)
    eval_sem.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT_FIXTURES)
    eval_sem.add_argument("--out", type=Path, help="write the JSON report here")

    eval_inj = sub.add_parser(
        "eval-injection", help="plant prompt injections in every fixture; outcomes must not change"
    )
    eval_inj.add_argument("--root", type=Path, default=DEFAULT_FIXTURES)
    eval_inj.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT_FIXTURES)
    eval_inj.add_argument(
        "--baseline", help="test a similarity baseline instead of a pipeline (needs --threshold)"
    )
    eval_inj.add_argument("--threshold", type=float, help="baseline threshold (e.g. from Phase 6)")
    eval_inj.add_argument("--view", choices=["added", "code"], default="added")
    eval_inj.add_argument("--out", type=Path, help="write the JSON report here")

    for command in (verify_fixture, verify_case, eval_fixtures, eval_inj):
        command.add_argument(
            "--pipeline",
            choices=sorted(PIPELINES),
            default=DEFAULT_PIPELINE,
            help=f"verification pipeline (default: {DEFAULT_PIPELINE})",
        )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
