"""Benchmark commands (Phase 9), registered by ``verireview.cli``.

    verireview benchmark-stats                        sizes, splits, targets
    verireview mine-candidates OWNER/REPO             resolved review threads (network, token)
    verireview collect-cases CANDIDATES.jsonl --n N --seed S   ingest a sample (network)
    verireview annotation-sheet --batch NAME [--calibration]   offline HTML page for annotators
    verireview agreement A.json B.json                Cohen's kappa + disagreements
    verireview adjudication-sheet A.json B.json --batch NAME   page for the adjudicator
    verireview build-gold A.json B.json [--adjudication ADJ.json]   write gold.json files
    verireview build-gold A.json --single-source model              provisional one-annotator gold
    verireview benchmark-freeze --version v1          write the frozen test manifest
    verireview eval-benchmark --split dev             Phase 10 ablation (test: --final-test-run)

Mining only works for repositories listed in ``dataset/benchmark/repositories.json``, which records
the project owner's approval (roadmap D9). Annotation pages embed third-party code, so they default
to ``dataset/raw/`` (not committed).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from verireview.benchmark import (
    CALIBRATION_CASES,
    AdjudicationFile,
    AnnotationFile,
    PendingAdjudicationError,
    agreement,
    build_gold,
    iter_real_world,
)
from verireview.benchmark.agreement import Kappa, single_annotator_gold
from verireview.benchmark.manifest import MANIFEST, FreezeError, freeze, stats
from verireview.benchmark.mining import (
    Candidate,
    LicenseNotAllowedError,
    collect,
    find_candidates,
)
from verireview.benchmark.sheet import Mode, render_sheet, sheet_case
from verireview.benchmark.store import REAL_WORLD, write_gold
from verireview.config import get_settings
from verireview.dataset import load_fixture
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.errors import GitHubError

DATASET = Path("dataset")
RAW = DATASET / "raw"
APPROVED = "benchmark/repositories.json"
COMMANDS = (
    "benchmark-stats",
    "mine-candidates",
    "collect-cases",
    "annotation-sheet",
    "agreement",
    "adjudication-sheet",
    "build-gold",
    "benchmark-freeze",
    "eval-benchmark",
)


def add_parsers(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("benchmark-stats", help="benchmark sizes, splits and targets")
    p.add_argument("--dataset", type=Path, default=DATASET)

    p = sub.add_parser("mine-candidates", help="find resolved review threads (needs a token)")
    p.add_argument("repo", help="OWNER/REPO (must be approved and permissively licensed)")
    p.add_argument("--max-prs", type=int, default=30, help="recent closed PRs to scan")
    p.add_argument("--out", type=Path, help="JSONL (default: dataset/raw/candidates/...)")
    p.add_argument("--dataset", type=Path, default=DATASET)

    p = sub.add_parser("collect-cases", help="ingest a seeded sample of candidates")
    p.add_argument("candidates", type=Path, nargs="+")
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--test-fraction", type=float, default=0.5)
    p.add_argument("--dataset", type=Path, default=DATASET)

    p = sub.add_parser("annotation-sheet", help="write the offline annotation page")
    p.add_argument("--batch", required=True, help="batch name, e.g. rw-v1")
    p.add_argument("--calibration", action="store_true", help="the 10 calibration fixtures")
    p.add_argument("--dataset", type=Path, default=DATASET)
    p.add_argument("--out", type=Path)

    p = sub.add_parser("agreement", help="inter-annotator agreement of two exports")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--out", type=Path, help="write the JSON report here")

    p = sub.add_parser("adjudication-sheet", help="page to resolve the disagreements")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--batch", required=True)
    p.add_argument("--dataset", type=Path, default=DATASET)
    p.add_argument("--out", type=Path)

    p = sub.add_parser("build-gold", help="write gold.json from two exports + adjudication")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path, nargs="?", help="second annotator (omit with --single-source)")
    p.add_argument("--adjudication", type=Path)
    p.add_argument(
        "--single-source",
        choices=["human", "model"],
        help="provisional gold from ONE annotator; never replaces existing human gold",
    )
    p.add_argument("--dataset", type=Path, default=DATASET)

    p = sub.add_parser("eval-benchmark", help="Phase 10 ablation study on a benchmark split")
    p.add_argument("--split", choices=["dev", "test"], required=True)
    p.add_argument(
        "--final-test-run",
        action="store_true",
        help="required for --split test: the frozen test split is evaluated once (Phase 10)",
    )
    p.add_argument("--systems", help="comma-separated subset (default: all pre-registered)")
    p.add_argument("--no-models", action="store_true", help="skip systems needing the nlp group")
    p.add_argument("--resamples", type=int, default=2000)
    p.add_argument("--protocol", type=Path, default=Path("docs/phase10_protocol.md"))
    p.add_argument("--dataset", type=Path, default=DATASET)
    p.add_argument("--out", type=Path)

    p = sub.add_parser("benchmark-freeze", help="write the frozen test-split manifest")
    p.add_argument("--version", required=True)
    p.add_argument("--dataset", type=Path, default=DATASET)


def run(args: argparse.Namespace) -> int:
    command = args.command
    if command == "benchmark-stats":
        return _stats(args.dataset)
    if command in ("mine-candidates", "collect-cases"):
        return _network(args)
    if command == "annotation-sheet":
        return _annotation_sheet(args.batch, args.calibration, args.dataset, args.out)
    if command == "agreement":
        return _agreement(_annotations(args.a), _annotations(args.b), args.out)
    if command == "adjudication-sheet":
        return _adjudication_sheet(args)
    if command == "build-gold":
        return _build_gold(args)
    if command == "eval-benchmark":
        return _eval_benchmark(args)
    return _freeze(args.version, args.dataset)


def _stats(dataset: Path) -> int:
    s = stats(dataset)
    print("case sets:        " + ", ".join(f"{k} {v}" for k, v in s.by_set.items()))
    print("source/split:     " + ", ".join(f"{k} {v}" for k, v in s.by_source_split.items()))
    print("test by category: " + ", ".join(f"{k} {v}" for k, v in s.test_by_category.items()))
    print("test by verdict:  " + ", ".join(f"{k} {v}" for k, v in s.test_by_verdict.items()))
    rw = s.real_world
    print(
        f"real-world:       collected {rw.collected} (dev {rw.dev}, test {rw.test}), "
        f"gold {rw.with_gold} (human {rw.human_gold}, provisional model {rw.model_gold}; "
        f"included {rw.included}, excluded {rw.excluded})"
    )
    print("\ntargets (v1):")
    for t in s.targets:
        print(f"  {'✓' if t.met else '✗'} {t.name:28} {t.actual:>4} / {t.required}")
    return 0


def _network(args: argparse.Namespace) -> int:
    settings = get_settings()
    client = GitHubClient(
        settings.github_token,
        api_url=settings.github_api_url,
        timeout_s=settings.github_timeout_s,
        max_retries=settings.github_max_retries,
    )
    try:
        with client:
            api = GitHubApi(client)
            if args.command == "mine-candidates":
                return _mine(api, args.repo, args.max_prs, args.out, args.dataset)
            candidates = [
                Candidate.model_validate_json(line)
                for path in args.candidates
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            report = collect(api, candidates, args.n, args.seed, args.dataset, args.test_fraction)
    except (GitHubError, LicenseNotAllowedError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"collected {len(report.written)} case(s) into {args.dataset / REAL_WORLD}")
    for key, reason in report.skipped.items():
        print(f"  skipped {key}: {reason}")
    return 0


def _mine(api: GitHubApi, repo_name: str, max_prs: int, out: Path | None, dataset: Path) -> int:
    repo = RepoRef(repo_name)
    approved = approved_repositories(dataset)
    if repo.full_name.lower() not in approved:
        print(
            f"error: {repo} is not approved for mining; add it to {dataset / APPROVED} "
            "once the project owner approves it",
            file=sys.stderr,
        )
        return 2
    found = list(find_candidates(api, repo, max_prs))
    out = out or RAW / "candidates" / f"{repo.owner}__{repo.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(c.model_dump_json() + "\n" for c in found), encoding="utf-8", newline="\n"
    )
    print(f"{repo}: {len(found)} candidate thread(s) from {max_prs} closed PRs -> {out}")
    return 0


def approved_repositories(dataset: Path) -> set[str]:
    path = dataset / APPROVED
    if not path.is_file():
        return set()
    return {r.lower() for r in json.loads(path.read_text(encoding="utf-8"))["repositories"]}


def _annotation_sheet(batch: str, calibration: bool, dataset: Path, out: Path | None) -> int:
    if calibration:
        cases = []
        for name in CALIBRATION_CASES:
            fixture = load_fixture(dataset / "fixtures" / name)
            reference = {
                "verdict": fixture.meta.expected_verdict.value,
                "rationale": fixture.meta.rationale,
                "requirements": [
                    {"category": r.category.value, "description": r.description}
                    for r in fixture.meta.requirements
                ],
            }
            cases.append(sheet_case(name, fixture.case, reference))
        mode: Mode = "calibration"
    else:
        root = dataset / REAL_WORLD
        pending = [rw for rw in iter_real_world(root) if rw.gold is None] if root.is_dir() else []
        cases = [sheet_case(rw.case_id, rw.case) for rw in pending]
        mode = "annotate"
    out = out or RAW / "sheets" / f"{batch}.html"
    _write(out, render_sheet(cases, batch, mode))
    print(f"wrote {out} ({len(cases)} case(s), mode {mode})")
    return 0


def _agreement(a: AnnotationFile, b: AnnotationFile, out: Path | None) -> int:
    report = agreement(a, b)
    print(f"{report.annotator_a} vs {report.annotator_b}: {report.common} common case(s)")
    if report.only_a or report.only_b:
        print(
            f"  only {report.annotator_a}: {len(report.only_a)}, "
            f"only {report.annotator_b}: {len(report.only_b)}"
        )
    for name, k in (
        ("inclusion", report.inclusion),
        ("verdict (4-class)", report.verdict),
        ("valid vs invalid", report.binary),
    ):
        print(f"  {name:24} {_kappa(k)}")
    for category, k in report.by_category.items():
        print(f"  verdict, {category:14} {_kappa(k)}")
    print(f"  disagreements to adjudicate: {len(report.disagreements)}")
    for d in report.disagreements:
        print(f"    {d.case_id}: {', '.join(d.fields)} ({d.a.verdict} vs {d.b.verdict})")
    if out is not None:
        _write(out, report.model_dump_json(indent=2) + "\n")
    return 0


def _adjudication_sheet(args: argparse.Namespace) -> int:
    a, b = _annotations(args.a), _annotations(args.b)
    disputed = [d.case_id for d in agreement(a, b).disagreements]
    root = args.dataset / REAL_WORLD
    cases = [
        sheet_case(rw.case_id, rw.case) for rw in iter_real_world(root) if rw.case_id in disputed
    ]
    pair = {
        "a": a.model_dump(mode="json"),
        "b": b.model_dump(mode="json"),
        "disputed": disputed,
    }
    out = args.out or RAW / "sheets" / f"{args.batch}-adjudication.html"
    _write(out, render_sheet(cases, args.batch, "adjudicate", pair))
    print(f"wrote {out} ({len(cases)} disputed case(s))")
    return 0


def _build_gold(args: argparse.Namespace) -> int:
    if (args.b is None) == (args.single_source is None):
        print("error: give two annotation files, or one with --single-source", file=sys.stderr)
        return 2
    if args.b is None:
        gold = single_annotator_gold(_annotations(args.a), args.single_source)
    else:
        adjudication = (
            AdjudicationFile.model_validate_json(args.adjudication.read_text(encoding="utf-8"))
            if args.adjudication
            else None
        )
        try:
            gold = build_gold(_annotations(args.a), _annotations(args.b), adjudication)
        except PendingAdjudicationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    root = args.dataset / REAL_WORLD
    existing = {rw.case_id: rw for rw in iter_real_world(root)}
    unknown = sorted(set(gold) - set(existing))
    if unknown:
        print(f"error: annotated cases not in {root}: {unknown}", file=sys.stderr)
        return 1
    kept = []
    for case_id, label in gold.items():
        current = existing[case_id].gold
        if label.label_source == "model" and current and current.label_source == "human":
            kept.append(case_id)  # a human label is never replaced by a model label
            continue
        write_gold(existing[case_id].directory, label)
    gold = {k: v for k, v in gold.items() if k not in kept}
    if kept:
        print(f"kept human gold for {len(kept)} case(s): {kept}")
    agreed = sum(g.agreed for g in gold.values())
    print(f"wrote gold for {len(gold)} case(s): {agreed} agreed, {len(gold) - agreed} adjudicated")
    return 0


def _freeze(version: str, dataset: Path) -> int:
    try:
        manifest = freeze(dataset, version)
    except FreezeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = dataset / MANIFEST
    _write(out, manifest.model_dump_json(indent=2) + "\n")
    print(
        f"froze {version}: {len(manifest.test_sets)} test set(s), "
        f"{len(manifest.real_world_test)} real-world test case(s) -> {out}"
    )
    return 0


def _eval_benchmark(args: argparse.Namespace) -> int:
    import hashlib

    from verireview.benchmark import Split, iter_benchmark
    from verireview.benchmark.manifest import Manifest, real_world_test_hash
    from verireview.evaluation import dataset_hash
    from verireview.evaluation.baselines import current_commit
    from verireview.evaluation.benchmark import (
        BOOTSTRAP_SEED,
        evaluate_system,
        paired_differences,
    )
    from verireview.evaluation.systems import SYSTEMS, BenchmarkReport

    if args.split == "test" and not args.final_test_run:
        print(
            "error: the test split is frozen and evaluated once (Phase 10); "
            "pass --final-test-run to run it",
            file=sys.stderr,
        )
        return 2
    wanted = {n.strip() for n in args.systems.split(",")} if args.systems else None
    unknown = sorted((wanted or set()) - {s.name for s in SYSTEMS})
    if unknown:
        print(f"error: unknown system(s) {unknown}", file=sys.stderr)
        return 2
    systems = [s for s in SYSTEMS if wanted is None or s.name in wanted]
    skipped = [s.name for s in systems if s.needs_models and args.no_models]
    systems = [s for s in systems if s.name not in skipped]

    split = Split(args.split)
    dev = list(iter_benchmark(args.dataset, Split.DEV))
    cases = dev if split == Split.DEV else list(iter_benchmark(args.dataset, Split.TEST))
    manifest_path = args.dataset / MANIFEST
    manifest = (
        Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else None
    )
    results = [evaluate_system(s, cases, dev, args.resamples) for s in systems]
    report = BenchmarkReport(
        split=split.value,
        commit=current_commit(),
        manifest_version=manifest.version if manifest else None,
        protocol_sha256=hashlib.sha256(args.protocol.read_bytes()).hexdigest()
        if args.protocol.is_file()
        else "missing",
        dataset_hashes=_split_hashes(args.dataset, cases, dataset_hash, real_world_test_hash),
        resamples=args.resamples,
        bootstrap_seed=BOOTSTRAP_SEED,
        n_cases=len(cases),
        systems=results,
        paired_vs_full=paired_differences(results, args.resamples),
        skipped=skipped,
    )
    _print_benchmark(report)
    if args.out is not None:
        _write(args.out, report.model_dump_json(indent=2) + "\n")
        print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


def _split_hashes(dataset: Path, cases: list, dataset_hash: Any, rw_hash: Any) -> dict[str, str]:  # type: ignore[type-arg]
    from verireview.benchmark import CASE_SETS

    used = {c.case_set for c in cases}
    hashes = {
        s.name: dataset_hash(dataset / s.path)
        for s in CASE_SETS
        if s.name in used and s.name != "real-world"
    }
    rw_ids = [c.fixture.meta.case_id for c in cases if c.case_set == "real-world"]
    if rw_ids:
        hashes["real-world (included cases)"] = rw_hash(dataset, rw_ids)
    return hashes


def _fmt(value: float | None) -> str:
    return "  n/a" if value is None else f"{value:.3f}"


def _ci(interval: Any) -> str:
    if interval.estimate is None:
        return "n/a"
    if interval.low is None:
        return f"{interval.estimate:.3f}"
    return f"{interval.estimate:.3f} [{interval.low:.2f}, {interval.high:.2f}]"


def _print_benchmark(report: Any) -> None:
    print(
        f"split {report.split}: {report.n_cases} cases; commit {report.commit[:8]}; "
        f"manifest {report.manifest_version}; protocol {report.protocol_sha256[:12]}; "
        f"bootstrap {report.resamples}x seed {report.bootstrap_seed}"
    )
    if report.skipped:
        print(f"skipped (no model group): {report.skipped}")
    print(
        f"\n{'system':7}{'accuracy [95% CI]':24}{'macro-F1 [95% CI]':24}"
        f"{'FAR [95% CI]':24}{'FBR [95% CI]':24}{'coverage':>9}{'sel.acc':>8}"
    )
    for r in report.systems:
        p = r.pooled
        print(
            f"{r.system:7}{_ci(p.intervals['accuracy']):24}{_ci(p.intervals['macro_f1']):24}"
            f"{_ci(p.intervals['false_acceptance_rate']):24}"
            f"{_ci(p.intervals['false_blocking_rate']):24}"
            f"{_fmt(p.coverage):>9}{_fmt(p.selective_accuracy):>8}"
        )
    sources = sorted({s for r in report.systems for s in r.by_source})
    for source in sources:
        n = next(r.by_source[source].n for r in report.systems if source in r.by_source)
        print(f"\n-- {source}: n={n}")
        print(f"{'system':7}{'acc':>7}{'mF1':>7}{'FAR':>7}{'FBR':>7}{'cov':>7}{'sel':>7}")
        for r in report.systems:
            sl = r.by_source.get(source)
            if sl is None:
                continue
            m = sl.metrics
            print(
                f"{r.system:7}{_fmt(m.accuracy):>7}{_fmt(m.macro_f1):>7}"
                f"{_fmt(m.false_acceptance_rate):>7}{_fmt(m.false_blocking_rate):>7}"
                f"{_fmt(sl.coverage):>7}{_fmt(sl.selective_accuracy):>7}"
            )
    if report.paired_vs_full:
        print("\npaired bootstrap, F minus X (95% CI):")
        for d in report.paired_vs_full:
            print(
                f"  vs {d.other:7} accuracy {_ci(d.accuracy):28} FAR {_ci(d.false_acceptance_rate)}"
            )
    full = next((r for r in report.systems if r.system == "F"), None)
    if full is not None:
        m = full.pooled.metrics
        print("\nF confusion (rows gold, cols predicted: SAT PART NOT UNC):")
        for gold, row in m.confusion.items():
            print(f"  {gold.value:22}" + "".join(f"{row[p]:5}" for p in row))
        print(
            "F accuracy by category:  "
            + ", ".join(f"{k} {v:.2f}" for k, v in full.pooled.accuracy_by_category.items())
        )
        print(
            "F accuracy by confidence: "
            + ", ".join(f"{k} {v:.2f}" for k, v in full.accuracy_by_confidence.items())
        )


def _annotations(path: Path) -> AnnotationFile:
    return AnnotationFile.model_validate_json(path.read_text(encoding="utf-8"))


def _kappa(k: Kappa) -> str:
    if k.n == 0:
        return "n=0"
    observed = f"{k.observed:.3f}" if k.observed is not None else "n/a"
    kappa = f"{k.kappa:.3f}" if k.kappa is not None else "undefined"
    return f"kappa {kappa}  (observed {observed}, n={k.n})"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


__all__ = ["COMMANDS", "add_parsers", "run"]
