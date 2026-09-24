# Phase 10.1: Evaluation Protocol for Benchmark v2 (pre-registered)

Written **after** the rule and extraction changes were finished on dev data, and **before** any
verifier (old or new) ran on the benchmark v2 test split. The test run happens once, with exactly
this protocol. Anything changed after seeing the results is reported as post-hoc and never
replaces these numbers. It reuses the Phase 10 protocol (`docs/phase10_protocol.md`) for metrics
and uncertainty; only what differs is stated here.

## Why a new test set

The Phase 10 test split (v1) was evaluated once and then used for error analysis, so the rule
changes of Phase 10.1 were motivated by it. It is dev data now. Benchmark v2 was frozen before
any rule change (`dataset/benchmark/v2/FREEZE_LOG.md`):

| Split | Sources | Cases | Labels |
|---|---|---|---|
| dev | `fixtures` (29), `heldout_fixtures` (24), all of v1 (`controlled` 60, `adversarial` 40, real-world 50) | 203 | author-written / provisional model (real-world) |
| **test** | `v2/controlled` (60), `v2/adversarial` (30), `v2/real_world` (57 of 60 included) | **147** | author-written blind (controlled, adversarial) / provisional model (real-world, fresh PRs not used in v1) |

Hashes are pinned in `dataset/benchmark/v2/manifest.json` and
`tests/benchmark/test_benchmark_v2.py`.

## Systems

| Name | What | Code |
|---|---|---|
| **F-old** | full VeriReview with the **Phase 10 rules** (`mvp-1`) | commit `1b530fa`, exported with `git archive` |
| F-gold-old | the same with gold requirements (diagnostic) | commit `1b530fa` |
| **F** | full VeriReview with the **Phase 10.1 rules** (`mvp-2`) | the Phase 10.1 working tree (source hash below) |
| F-gold | the same with gold requirements (diagnostic) | Phase 10.1 |
| A, B, B′, L, S, R, C/D, E | the Phase 10 ablation rows, as defined there | Phase 10.1 (thresholds of A, B, B′: Youden's J on the v2 **dev** split) |

The Phase 10 code only knows the v1 dataset layout, so for F-old the v2 test sets are copied, unchanged,
into a temporary v1-shaped directory (`benchmark/controlled` ← `v2/controlled`,
`benchmark/adversarial` ← `v2/adversarial`, `benchmark/real_world` ← `v2/real_world`; dev from
`fixtures` and `heldout_fixtures`). F and F-old are evaluated on exactly the same case ids and
gold labels; `verireview compare-reports` refuses to compare otherwise.

The Phase 10.1 rules are frozen at this source hash, taken before the run. The working tree is
uncommitted at run time (the owner commits after the phase), so the report's `commit` field says
`1b530fa`; this hash identifies the code instead. It is sha256 over every
`src/verireview/**/*.py`, sorted by POSIX path, feeding `path + NUL + file bytes + NUL`:

```text
SOURCE_SHA256 = 287fca5ee86ec2a6c11ca361397b5bac3f1b58fdf681541b6edba94de88b1b0c
```

Recompute it with:

```python
import hashlib
from pathlib import Path

h = hashlib.sha256()
for p in sorted(Path("src/verireview").rglob("*.py"), key=lambda p: p.as_posix()):
    h.update(p.as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
print(h.hexdigest())
```

## Metrics and uncertainty

As in Phase 10: accuracy, macro-F1, FAR, FBR, coverage, selective accuracy, per source and
pooled; 95% percentile bootstrap, 2,000 resamples, seed 20260924. **New:** paired bootstrap of
F − F-old (same resampled cases) for accuracy, FAR, FBR and coverage, pooled and per source.

## Primary questions (decided in advance)

1. **Improvement:** is F's accuracy on v2 test higher than F-old's, with the paired interval
   excluding 0?
2. **Safety:** is F's false acceptance rate not higher than F-old's? Counted as met if the paired
   FAR difference is ≤ 0 as an estimate and its upper bound is ≤ +0.05.
3. **Real-world:** coverage and selective accuracy of F on the fresh real-world cases (provisional
   labels, reported separately), compared with F-old.
4. **Generalisation gap:** F's dev-versus-test gap, compared with the Phase 10 gap (dev 1.0 /
   held-out 0.875 versus test 0.483).

Everything else (the ablation rows, per-category and per-adversarial-type accuracy) is
descriptive.

## Procedure

1. Freeze this protocol: fill in `SOURCE_SHA256`, record the protocol's own sha256 in the run.
2. F-old (once):
   `git archive 1b530fa src docs/phase10_protocol.md` into a scratch directory, build the
   v1-shaped copy of the v2 test sets, then with that export's `src` first on `PYTHONPATH` (same
   dependencies; Phase 10.1 added none):
   `verireview eval-benchmark --split test --final-test-run --systems F,F-gold --no-models
   --dataset <copy> --out experiments/phase10_1_test_old_rules.json`.
3. F and the ablation (once):
   `verireview eval-benchmark --split test --final-test-run --benchmark-version v2
   --protocol docs/phase10_1_protocol.md --out experiments/phase10_1_test.json`.
4. `verireview compare-reports experiments/phase10_1_test_old_rules.json
   experiments/phase10_1_test.json --system F --out experiments/phase10_1_test_paired.json`, and
   the same with `--system F-gold`.
5. Report the numbers as they are, including a descriptive error analysis. Fixes motivated by the
   v2 test cases belong to a later phase with a new test set (v3); v2 then becomes dev data.

## Known limitations, stated in advance

- v2 `controlled` and `adversarial` were written by the same author as the rules, after the v1
  error analysis, from the same recipe. Targeting cannot be ruled out; the fresh real-world cases
  are the independent part.
- Real-world labels are provisional (one model annotator, blind). Human labels replace them later.
- A single run: no variance over rule versions, only over cases (bootstrap).
