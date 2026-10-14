# Phase 10.3: Evaluation Protocol for Benchmark v3 (pre-registered)

Written **after** the rule and extraction changes were finished on dev data, and **before** any
verifier (old or new) ran on the benchmark v3 test split. The test run happens once, with exactly
this protocol. Anything changed after seeing the results is reported as post-hoc and never
replaces these numbers. It reuses the Phase 10 protocol (`docs/phase10_protocol.md`) for metrics
and uncertainty, and the Phase 10.1 protocol (`docs/phase10_1_protocol.md`) for the old-versus-new
design. Only what differs is stated here.

## Why a new test set

The v2 test split was evaluated once in Phase 10.1 and then used for error analysis, and its
real-world labels were replaced by one human annotator's labels in Phase 10.2. It is dev data now.
Benchmark v3 was frozen on 2026-10-13, before any rule change (`dataset/benchmark/v3/FREEZE_LOG.md`):

| Split | Sources | Cases | Labels |
|---|---|---|---|
| dev | `fixtures` (29), `heldout_fixtures` (24), all of v1 and v2 | 345 | author-written; real-world: v1 provisional model, v2 one human annotator |
| **test** | `v3/controlled` (60), `v3/adversarial` (30), `v3/real_world` (58 of 60 included) | **148** | author-written blind (controlled, adversarial); real-world: **one human annotator**, not adjudicated, fresh PRs not used before |

Hashes are pinned in `dataset/benchmark/v3/manifest.json` and
`tests/benchmark/test_benchmark_v3.py`. No verifier has run on any v3 test case, and no verifier
output for them has been looked at.

## What changed (on dev only)

Error analysis was done only on dev cases (mostly the v2 cases, now dev, including the v2
real-world cases with the human labels).

- Unreachable code: checks, handlers and `with suppress(...)` after an unconditional return or
  raise do not count.
- A status object built but neither raised nor returned (`HTTPException(404)` as a statement)
  does not count. `abort(404)` still does.
- Validation:
  - Polarity: a range check must reject what the request rejects. It is evaluated on sample
    values without executing anything.
  - A check behind an unrelated flag (`if DEBUG and …`) is not satisfied when the flag is a
    false module constant, and inconclusive when the flag's value is unknown.
  - "are dates", "is a list" ask for a type check.
- Error handling: a call named as `open()` must be the protected one.
- Testing:
  - A new test in a file that test runners do not collect is inconclusive.
  - A scenario described only in words that the test never mentions is inconclusive.
- Extraction:
  - "more gracefully" / "properly" with no target is ambiguous.
  - A comment with no other request that calls the commented code superfluous ("No longer
    used", "can be left out", "duplicates the line above") is a removal request.
- `other`: "add `# GH#63221`" (an exact comment in backticks) is checked.

Pipelines are renamed `mvp-3`, `phase5-rules-3`, `phase7-semantic-3`. On dev:

| Check | Before (commit a71e55c) | After |
|---|---|---|
| Dev split F (345) | acc 0.739, FAR 0.061, FBR 0.018, coverage 0.704 | acc 0.771, FAR 0.007, FBR 0.018, coverage 0.707 |
| Cases changed | | 11 fixed, 0 broken, 2 still wrong but changed |
| Dev fixtures (29) | 1.000, FAR 0 | 1.000, FAR 0 |
| Held-out verdict fixtures (24) | 0.917, FAR 0, FBR 0.071 | 0.917, FAR 0, FBR 0.071 |
| Held-out requirements | count 0.938, category F1 0.974 | unchanged |
| Prompt injection | 0 changes | 0/708 (`mvp`), 0/708 (`phase7-semantic`) |

Reports: `experiments/phase10_3_dev_before.json` and `experiments/phase10_3_dev.json`.

## Systems

| Name | What | Code |
|---|---|---|
| **F-old** | full VeriReview with the **Phase 10.1 rules** (`mvp-2`) | commit `a71e55c` (the v3 freeze), exported with `git archive` |
| F-gold-old | the same with gold requirements (diagnostic) | commit `a71e55c` |
| **F** | full VeriReview with the **Phase 10.3 rules** (`mvp-3`) | the Phase 10.3 working tree (source hash below) |
| F-gold | the same with gold requirements (diagnostic) | Phase 10.3 |
| A, B, B′, L, S, R, C/D, E | the Phase 10 ablation rows, as defined there | Phase 10.3 (thresholds of A, B, B′: Youden's J on the v3 **dev** split) |

Commit `a71e55c` already knows the v3 layout, so F-old runs on the v3 test split directly, with
no copy. F and F-old are evaluated on the same case ids and gold labels.
`verireview compare-reports` refuses to compare otherwise. The models for L, S, R and E are read
from the local cache (`HF_HUB_OFFLINE=1`); all systems were dry-run on dev first.

The Phase 10.3 rules are frozen at this source hash, taken before the run. The working tree is
uncommitted at run time (the owner commits after the phase), so the report's `commit` field says
`a71e55c`; this hash identifies the code instead. It is sha256 over every
`src/verireview/**/*.py` (113 files), sorted by POSIX path, feeding `path + NUL + file bytes + NUL`
(the recipe of `docs/phase10_1_protocol.md`):

```text
SOURCE_SHA256 = 211a02c7d119a49f0d211cfb13a1da1033649cc7c2b60ced6847fe30895bc1b5
```

## Metrics and uncertainty

As in Phase 10 and 10.1:
- accuracy, macro-F1, FAR, FBR, coverage and selective accuracy, per source and pooled;
- 95% percentile bootstrap, 2,000 resamples, seed 20260924;
- paired bootstrap of F − F-old (same resampled cases) for accuracy, FAR, FBR and coverage,
  pooled and per source.

## Primary questions (decided in advance)

1. **Improvement:** is F's accuracy on the v3 test higher than F-old's, with the paired interval
   excluding 0? Most changes target false acceptance, not accuracy, so a small or unclear
   accuracy gain is a possible, honest outcome.
2. **Safety:** is F's false acceptance rate not higher than F-old's? It counts as met if the
   paired FAR difference is ≤ 0 as an estimate and its upper bound is ≤ +0.05.
3. **Real-world:** F's coverage and selective accuracy on the fresh real-world cases, compared
   with F-old. Labels are from **one human annotator**, not adjudicated, and are reported
   separately.
4. **Generalisation gap:** F's gap between dev (0.771) and test, compared with Phase 10.1's gap
   (dev 0.798 against test 0.653, 0.145).

Everything else is descriptive: the ablation rows, per-category accuracy and per-adversarial-type
accuracy.

## Procedure

1. Freeze this protocol: fill in `SOURCE_SHA256`, and record the protocol's own sha256 in both
   runs (`--protocol`).
2. F-old (once): `git archive a71e55c src` into a scratch directory. Then, with that export's
   `src` first on `PYTHONPATH` (same dependencies, since Phase 10.3 added none):
   `verireview eval-benchmark --split test --final-test-run --systems F,F-gold --no-models
   --protocol docs/phase10_3_protocol.md --out experiments/phase10_3_test_old_rules.json`.
3. F and the ablation (once):
   `HF_HUB_OFFLINE=1 uv run --group nlp verireview eval-benchmark --split test --final-test-run
   --protocol docs/phase10_3_protocol.md --out experiments/phase10_3_test.json`.
4. `verireview compare-reports experiments/phase10_3_test_old_rules.json
   experiments/phase10_3_test.json --system F --out experiments/phase10_3_test_paired.json`.
   Then the same with `--system F-gold` (`…_paired_gold.json`).
5. Report the numbers as they are, with a descriptive error analysis. Fixes motivated by the v3
   test cases belong to a later phase with a new test set (v4), frozen before the changes. v3
   then becomes dev data.

## Known limitations, stated in advance

- The v3 `controlled` and `adversarial` cases were written by the same author as the rules (Claude,
  in Phase 10.2, before these changes), from the same recipe as v2. The rule changes were made
  from dev cases only, but the author had written the test cases. Targeting cannot be ruled out.
  The fresh real-world cases are the independent part.
- Real-world labels come from one human annotator, not adjudicated, with no human–human kappa.
- 9 of the 58 real-world test cases are labelled uncertain by the annotator. Of the rest, 5 are
  not satisfied, so FAR on real-world alone rests on very few cases.
- A single run: the only variance measured is over cases (bootstrap), not over rule versions.
