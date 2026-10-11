# Phase 10.2: Human Labels for v2, and Building Benchmark v3

Two things, in this order:

1. The provisional Claude labels of the v2 real-world test cases were replaced by a human
   annotator's labels, and the recorded v2 run was re-scored against them (no new run).
2. Benchmark v3 is being built, so that the v2 test split can become dev data and the rules can
   be improved on it. **No rule was changed in this phase.**

Owner decisions (2026-10-11): record the one annotator's labels as the v2 real-world gold; collect
new real-world cases from the six approved repositories; the annotators label them.

## 1. Human labels for the v2 real-world cases

One annotator (Jordan) labelled all 60 cases blind, on the page from
`annotation-sheet --batch rw-v2 --relabel-model`, which never shows the model's labels. The raw
export is `dataset/annotations/jordan/rw-v2.json` (unedited). It became the gold with
`build-gold dataset/annotations/jordan/rw-v2.json --single-source human`.

**This is one annotator.** The labels are not adjudicated, and agreement between two humans
cannot be measured. What can be measured is the human against the earlier model labels.

### The human against the provisional model labels

Real output of `verireview agreement dataset/annotations/claude/rw-v2.json dataset/annotations/jordan/rw-v2.json`:

```text
claude vs Jordan: 60 common case(s)
  inclusion                kappa -0.078  (observed 0.817, n=60)
  verdict (4-class)        kappa 0.599  (observed 0.878, n=49)
  valid vs invalid         kappa 0.633  (observed 0.932, n=44)
  verdict, other          kappa 0.869  (observed 0.955, n=22)
  verdict, testing        kappa 0.000  (observed 0.667, n=9)
  disagreements to adjudicate: 21
```

- **Verdicts:** the same on 43 of the 49 cases both included (kappa 0.599, at the 0.6 target that
  was set for two humans).
- **Inclusion:** they differ on 11 of 60. The human excluded 8 cases the model kept (all as "no
  requirement") and kept 3 the model excluded. Kappa is near zero because almost every case is
  included by both, and the few exclusions do not overlap.
- **The model labels were lenient.** Among the 49 common cases the human found 7 not satisfied,
  the model 3. In three cases the model said SATISFIED and the human NOT_SATISFIED.

### The recorded v2 run against the human labels

The run of Phase 10.1 (`experiments/phase10_1_test.json`) was **not** repeated. Its stored
predictions were scored against the current labels. Real output of
`verireview rescore-report experiments/phase10_1_test.json` (saved as
`experiments/phase10_2_v2_rescored_human_labels.json`):

```text
F of phase10_1_test.json against the current real-world labels (v2: human 60); stored predictions, no verifier run
  pooled     as recorded                  n=147  acc 0.653 [0.58, 0.73]  FAR 0.151 [0.06, 0.26]  FBR 0.037  cov 0.680  right-when-decided 0.840
  pooled     same cases, recorded labels  n=139  acc 0.655 [0.58, 0.73]  FAR 0.151 [0.06, 0.26]  FBR 0.041  cov 0.691  right-when-decided 0.833
  pooled     same cases, current labels   n=139  acc 0.662 [0.58, 0.74]  FAR 0.158 [0.07, 0.26]  FBR 0.029  cov 0.691  right-when-decided 0.833
  real-world as recorded                  n= 57  acc 0.456 [0.33, 0.60]  FAR 0.000 [0.00, 0.00]  FBR 0.020  cov 0.439  right-when-decided 0.920
  real-world same cases, recorded labels  n= 49  acc 0.429 [0.29, 0.57]  FAR 0.000 [0.00, 0.00]  FBR 0.023  cov 0.429  right-when-decided 0.905
  real-world same cases, current labels   n= 49  acc 0.449 [0.31, 0.59]  FAR 0.143 [0.00, 0.50]  FBR 0.000  cov 0.429  right-when-decided 0.905
  excluded by the current labels: 8; included now but never run (no stored prediction, not scored): 3; verdict changed: 6
    home-assistant__core__165993__3024038116: SATISFIED -> NOT_SATISFIED (predicted UNCERTAIN)
    pandas-dev__pandas__64535__3555961427: SATISFIED -> UNCERTAIN (predicted UNCERTAIN)
    pandas-dev__pandas__64535__3574519955: SATISFIED -> UNCERTAIN (predicted NOT_SATISFIED)
    pandas-dev__pandas__64535__3759896069: SATISFIED -> NOT_SATISFIED (predicted UNCERTAIN)
    pydantic__pydantic__13523__3677536114: UNCERTAIN -> NOT_SATISFIED (predicted NOT_SATISFIED)
    pydantic__pydantic__13690__3842248596: SATISFIED -> NOT_SATISFIED (predicted SATISFIED)
```

Reading it (the two "same cases" rows are comparable; "as recorded" has other cases):

| Real-world, the 49 cases both label sets include | Model labels | Human labels |
|---|---|---|
| Accuracy | 0.429 | 0.449 |
| Decided (coverage) | 21 of 49 | 21 of 49 |
| Right when decided | 19 of 21 | 19 of 21 |
| Bad resolutions accepted (FAR) | 0 of 3 | **1 of 7** |
| Good resolutions rejected (FBR) | 1 of 43 | 0 of 38 |

- **One real-world false acceptance was hidden by the model labels.** In
  `pydantic__pydantic__13690__3842248596` the model label and the verifier both said SATISFIED; the
  human says NOT_SATISFIED. This is the shared blind spot that the provisional labels were
  expected to have (the labeller also wrote the rules). The Phase 10.1 statement "no false
  acceptance on real-world cases" holds for the model labels only.
- **Pooled numbers barely move** (accuracy 0.655 → 0.662, FAR 0.151 → 0.158, on the same 139
  cases). The real-world numbers rest on 7 bad cases: the interval of that FAR is 0.00–0.50.
- **Three cases only the human includes were never run**, so they have no prediction and are not
  scored. They are run once v2 is dev data.
- **Unsettled.** Where the human and the model disagree, one annotator cannot say who is right.
  A second annotator on the 21 disputed cases would settle that and give a human–human kappa.

### What changed in the frozen v2 test split

Only the 60 `gold.json` files (`dataset/benchmark/v2/FREEZE_LOG.md`, entry 6). The cases are
unchanged and are now pinned separately from their labels
(`test_v2_real_world_cases_are_unchanged_by_the_relabelling`); a second test pins that the gold is
human and from one annotator. `benchmark-stats` now shows how many human labels come from a single
annotator. The enforcement gate file (`enforcement/eligibility.json`) is **not** regenerated: it
is computed from the recorded run, and no category is eligible either way.

## 2. Benchmark v3

The order is the one of v2 (`dataset/benchmark/v2/FREEZE_LOG.md`): the new test split is frozen
**before** any rule changes, and only then does the v2 test split become dev data.

- **Layout** (`benchmark/store.py`, `V3`): the v2 sets are dev; the test sets live in
  `dataset/benchmark/v3/`. v2 stays the current version until v3 is frozen, and
  `eval-benchmark --benchmark-version v3` refuses to run before `v3/manifest.json` exists
  (`tests/benchmark/test_benchmark_v3.py`).
- **Real-world collection:** the rule was written into `dataset/benchmark/v3/FREEZE_LOG.md`
  before any case was collected: fresh pull requests only (none used in v1 or v2), all in the test
  split, 10 per repository with a fixed top-up rule, and at most 3 threads per pull request
  (`collect-cases --max-per-pull 3`, new: in v2 one pull request supplied 7 of the 60 cases).
  Result: **60 cases from 45 pull requests** (httpx 11, home-assistant 11, click 11, pandas 7,
  pydantic 10, pytest 10; pandas ran short because of its very large files).
- **Labels:** by the human annotators. `annotation-sheet --batch rw-v3 --benchmark-version v3`
  writes the page with all 60; `--cases FILE` (new) writes a page with chosen cases, used for a
  two-annotator split (20 shared, 20 + 20). Nothing has run on these cases, and nothing will
  before they are labelled and frozen.
- **A second opinion on v2** (optional): `rw-v2-second.html`, 36 cases: the 21 where the human
  and the model labels disagree plus 15 drawn at random (seed 20261011) from the other 39. The
  random 15 give an unbiased look at human–human agreement; the 21 settle the disputes.

- **Controlled (60) and adversarial (30) cases:** written blind (no verifier ran on them; they
  were only loaded and compiled) and pinned by hash in `tests/benchmark/test_benchmark_v3.py`
  before any rule change. Same recipe as v1 and v2, checked by a test against v2: 12 and 6 cases
  per category, the same verdict mix, and the same number of every difficult-case type (prompt
  injection, dead code, wrong value, wrong target, text that only mentions the fix, unusual but
  valid idioms, partial fixes). Same caveat as before: they come from the rules' author.

Still to do before the freeze: the human labels for the 60 new real-world cases; then
`benchmark-freeze --benchmark-version v3`. After that: rule changes on dev data, and one blind v3
run under a pre-registered protocol.

## Commands

```bash
uv run verireview agreement dataset/annotations/claude/rw-v2.json dataset/annotations/jordan/rw-v2.json
uv run verireview build-gold dataset/annotations/jordan/rw-v2.json --single-source human
uv run verireview rescore-report experiments/phase10_1_test.json --out experiments/phase10_2_v2_rescored_human_labels.json
uv run verireview mine-candidates OWNER/REPO --max-prs 250 --out dataset/raw/candidates/v3/OWNER__REPO.jsonl
uv run verireview collect-cases FILES… --n 10 --seed 20261011 --test-fraction 1.0 --max-per-pull 3 --benchmark-version v3
uv run verireview annotation-sheet --batch rw-v3 --benchmark-version v3
uv run verireview annotation-sheet --batch rw-v3-shared --benchmark-version v3 --cases dataset/raw/sheets/rw-v3-shared.ids.txt
```

## Limitations

- **One annotator for v2.** No adjudication, no human–human agreement. The v1 real-world cases
  (now dev data) still have provisional model labels.
- **Small numbers.** Seven bad real-world resolutions among 49 cases; one false acceptance.
- **The v2 test split is still locked.** Nothing here used it to change a rule.
