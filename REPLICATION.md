# Replication Package

This repository is the replication package for VeriReview. It contains:
- the code;
- the frozen benchmarks and their human labels;
- the pre-registered protocols;
- every recorded evaluation report.

This file says how to repeat each published number, and what was verified.

## 1. Verified on 2026-10-14

Each recorded blind test run was re-run from the commit at which it was recorded, on the dataset
of that commit. Predictions, gold labels and confidences are **identical for every case**, and the
bootstrap intervals are identical too:

| Round | Recorded report | Commit | Cases identical | Accuracy / FAR (reproduced) |
|---|---|---|---|---|
| 1 (v1 test) | `experiments/phase10_test.json` | `1b530fa` | 120 / 120 | 0.483 [0.39, 0.57] / 0.237 [0.14, 0.35] |
| 2 (v2 test) | `experiments/phase10_1_test.json` | `cdb7ff0` | 147 / 147 | 0.653 [0.58, 0.73] / 0.151 [0.06, 0.26] |
| 3 (v3 test) | `experiments/phase10_3_test.json` | `c3f20ae` | 148 / 148 | 0.568 [0.49, 0.64] / 0.088 [0.02, 0.17] |

- The round-3 source hash at `c3f20ae` equals the pre-registered `SOURCE_SHA256` in
  `docs/phase10_3_protocol.md` (`211a02c7d119…`).
- Each report records the hash of its protocol (`protocol_sha256`).
- Verified systems: F (full VeriReview) and F-gold (with gold requirements). The baselines (A, B,
  B′, L, S, R, C/D, E) were not re-run for this check; section 4.1 shows how.

## 2. Environment

- Python 3.13 and [uv](https://docs.astral.sh/uv/) (checked with uv 0.12.18). Dependencies are
  locked in `uv.lock`; Tree-sitter is pinned (`tree-sitter~=0.26.0`, `tree-sitter-python~=0.25.0`).
- Evaluation needs no database, Docker, network or GitHub token.
- Optional `nlp` group for the model baselines: `sentence-transformers/all-MiniLM-L6-v2`, and
  UniXcoder (`microsoft/unixcoder-base`) pinned at revision
  `5604afdc964f6c53782a6813140ade5216b99006`.
- Checked on Windows 11. The commands are the same on Linux and macOS (use `PYTHONPATH=…` as
  shown).

```bash
uv sync
uv run pytest            # 1,266 unit and benchmark tests, including the dataset hash pins
```

## 3. What is in the package

| Path | Contents |
|---|---|
| `dataset/fixtures`, `dataset/heldout_fixtures` | 29 dev and 24 held-out hand-written cases |
| `dataset/benchmark/{controlled,adversarial,real_world}` | benchmark v1 (manifest `dataset/benchmark/manifest.json`) |
| `dataset/benchmark/v2/…`, `dataset/benchmark/v3/…` | benchmarks v2 and v3, each with `manifest.json` and `FREEZE_LOG.md` (order of events, every label change) |
| `dataset/benchmark/*/real_world/<case>/` | `case.json` (pseudonymised thread, code before and after, diff), `provenance.json`, `gold.json` |
| `dataset/annotations/<name>/` | raw annotation exports, never edited (Claude provisional; Jordan; Nandha; the adjudication) |
| `dataset/benchmark/LICENSES/` | licences of the six source repositories |
| `docs/phase10_protocol.md`, `phase10_1_protocol.md`, `phase10_3_protocol.md` | pre-registered protocols |
| `experiments/*.json` | every recorded report (dev, test, paired comparisons, re-scorings) |
| `tests/benchmark/` | hash pins for every frozen set; held-out FAR = 0; prompt-injection suite |

Not included:
- the offline annotation pages (`dataset/raw/`, git-ignored, because they embed third-party code);
  rebuild them with `verireview annotation-sheet`;
- the raw mining candidates;
- secrets of any kind.

## 4. Repeating each result

### 4.1 The three blind test runs (old code, data as it was)

Each run is repeated from its own commit, exported with `git archive`, because later phases
changed the rules, and also the v2 labels. The commands below are for round 3; for rounds 1
and 2, use commit `1b530fa` or `cdb7ff0`, the matching protocol, and for round 2
`--benchmark-version v2`.

```bash
git archive c3f20ae src dataset docs | tar -x -C /tmp/vr-round3
cd /tmp/vr-round3
PYTHONPATH=src uv run --project <this repository> verireview eval-benchmark --split test --final-test-run \
    --systems F,F-gold --no-models --protocol docs/phase10_3_protocol.md --dataset dataset --out repro.json
```

Compare `repro.json` with `experiments/phase10_3_test.json`: the per-case `expected`,
`predicted` and `confidence` must be equal. The full ablation, including the model baselines,
adds `uv run --group nlp` and drops `--systems … --no-models`.

These are reproductions of recorded runs with the same code. They are **not** new attempts: no
rule may be tuned against these test sets (see `CLAUDE.md`).

### 4.2 Paired old-against-new comparisons and re-scorings (no verifier run)

```bash
uv run verireview compare-reports experiments/phase10_3_test_old_rules.json experiments/phase10_3_test.json --system F
uv run verireview compare-reports experiments/phase10_1_test_old_rules.json experiments/phase10_1_test.json --system F
uv run verireview rescore-report experiments/phase10_1_test.json --system F     # v2 run against the adjudicated labels
```

### 4.3 Development results (current code)

```bash
uv run verireview eval-fixtures                                   # 29 dev fixtures: 1.000, FAR 0
uv run verireview eval-fixtures --root dataset/heldout_fixtures   # 24 held-out: 0.917, FAR 0
uv run verireview eval-requirements                               # extraction: dev and held-out
uv run verireview eval-injection                                  # 0 of 708 / 580 outcomes changed
uv run --group nlp verireview eval-injection --pipeline phase7-semantic
uv run verireview eval-benchmark --split dev --systems F,F-gold --no-models   # 345 dev cases
uv run --group nlp verireview eval-baselines --scorers lexical,tfidf,embedding,unixcoder --views added,code
```

Since Phase 10.3 the v2 real-world labels changed (second annotator and adjudication). Dev
results computed today therefore differ slightly from `experiments/phase10_3_dev.json`, which
records the labels of that day.

### 4.4 Human-label agreement

```bash
uv run verireview agreement dataset/annotations/claude/rw-v2.json dataset/annotations/jordan/rw-v2.json
uv run verireview agreement dataset/annotations/jordan/rw-v2.json dataset/annotations/nandha/annotations-Nandha-rw-v2-second.json
```

### 4.5 The enforcement gate

```bash
uv run verireview enforcement-eligibility experiments/phase10_3_test.json   # read-only: eligible none
```

## 5. Where each number in the report comes from

| Claim | Source |
|---|---|
| Three blind rounds (accuracy, FAR, intervals) | `experiments/phase10_test.json`, `phase10_1_test.json`, `phase10_3_test.json` |
| Old against new, paired | `experiments/phase10_1_test_paired.json`, `phase10_3_test_paired.json` |
| Baselines on v3 | `experiments/phase10_3_test.json` (systems A, B, B′, L, S, R) |
| Dev 0.739 → 0.771; 11 fixed, 0 broken | `experiments/phase10_3_dev_before.json`, `phase10_3_dev.json` |
| 0 of 2,576 injection outcomes changed | `eval-injection` output; `tests/benchmark/test_prompt_injection.py` |
| κ 0.60 (human vs model), κ 0.33 (human vs human) | `verireview agreement` (section 4.4); `docs/phase10_2_human_labels_v3.md` |
| v2 real-world re-scored: 0 of 4 bad accepted | `experiments/phase10_2_v2_rescored_adjudicated.json` |
| Threats and limitations | `docs/threats_to_validity.md` |

## 6. Licence and data use

- The real-world cases are pseudonymised extracts from projects with permissive licences; their
  licence texts are in `dataset/benchmark/LICENSES/`.
- **The repository has no licence for its own code yet.** Choosing one (and the question of a
  patent filing) is the owner's decision and should come before the repository is made public.
