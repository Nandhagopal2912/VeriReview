# Phase 10.2: Human Labels for v2, and Benchmark v3 Frozen

Two things, in this order:

1. The provisional Claude labels of the v2 real-world test cases were replaced by a human
   annotator's labels, and the recorded v2 run was re-scored against them (no new run).
2. Benchmark v3 was built and **frozen** (2026-10-13), so that the v2 test split is dev data now
   and the rules can be improved on it. **No rule was changed in this phase, and no verifier has
   run on any v3 test case.**

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
  `dataset/benchmark/v3/`. While v3 was being built, v2 stayed the current version, and
  `eval-benchmark` refused v3 because it had no manifest. That guard stays for any later version
  (`test_a_version_without_a_manifest_cannot_be_evaluated`).
- **Real-world collection:** the rule was written into `dataset/benchmark/v3/FREEZE_LOG.md`
  before any case was collected: fresh pull requests only (none used in v1 or v2), all in the test
  split, 10 per repository with a fixed top-up rule, and at most 3 threads per pull request
  (`collect-cases --max-per-pull 3`, new: in v2 one pull request supplied 7 of the 60 cases).
  Result: **60 cases from 45 pull requests** (httpx 11, home-assistant 11, click 11, pandas 7,
  pydantic 10, pytest 10; pandas ran short because of its very large files).
- **Labels:** one human annotator (Jordan) labelled all 60 blind on the page from
  `annotation-sheet --batch rw-v3 --benchmark-version v3`; the raw export is
  `dataset/annotations/jordan/rw-v3.json`. 58 included, 2 excluded; 42 satisfied, 2 partially
  satisfied, 5 not satisfied, 9 uncertain; 32 of the 58 main requests are `other`. No verifier
  had run on the cases. As for v2, this is **one annotator**: not adjudicated. (`--cases FILE`,
  new, writes a page with chosen cases, for a two-annotator split; it was prepared and not
  needed.)
- **A second opinion on v2** (optional): `rw-v2-second.html`, 36 cases: the 21 where the human
  and the model labels disagree plus 15 drawn at random (seed 20261011) from the other 39. The
  random 15 give an unbiased look at human–human agreement; the 21 settle the disputes.

- **Controlled (60) and adversarial (30) cases:** written blind (no verifier ran on them; they
  were only loaded and compiled) and pinned by hash in `tests/benchmark/test_benchmark_v3.py`
  before any rule change. Same recipe as v1 and v2, checked by a test against v2: 12 and 6 cases
  per category, the same verdict mix, and the same number of every difficult-case type (prompt
  injection, dead code, wrong value, wrong target, text that only mentions the fix, unusual but
  valid idioms, partial fixes). Same caveat as before: they come from the rules' author.

### The freeze (2026-10-13)

`benchmark-freeze --benchmark-version v3` wrote `dataset/benchmark/v3/manifest.json`; the hashes
are pinned in `tests/benchmark/test_benchmark_v3.py` (the two authored sets, the real-world cases
with their labels, and the cases alone). `CURRENT_VERSION` is `v3`. Real output of
`verireview benchmark-stats`:

```text
benchmark v3
case sets:        dev-fixtures 29, dev-heldout 24, v1-controlled 60, v1-adversarial 40, v1-real-world 50, v2-controlled 60, v2-adversarial 30, v2-real-world 52, controlled 60, adversarial 30, real-world 58
source/split:     controlled/dev 173, adversarial/dev 70, real_world/dev 102, controlled/test 60, adversarial/test 30, real_world/test 58
test by category: naming 19, validation 21, testing 27, error_handling 20, api_behavior 29
test by verdict:  SATISFIED 72, PARTIALLY_SATISFIED 17, NOT_SATISFIED 40, UNCERTAIN 19
real-world:       collected 60 (dev 0, test 60), gold 60 (human 60, of which one annotator 60; provisional model 0; included 58, excluded 2)
```

| | Test (frozen, unused) | Dev (may be studied and tuned on) |
|---|---|---|
| Controlled | 60 | 173 |
| Adversarial | 30 | 70 |
| Real-world | 58 (human labels, one annotator) | 102 (52 human labels, one annotator; 50 provisional model labels) |
| **Total** | **148** | **345** |

Naming has 19 test cases against a target of 20 (real-world requests are mostly `other`);
recorded, not padded.

**What comes next (a new phase):** an error analysis of the dev data, including the v2 cases with
their human labels; rule changes on dev data only; a pre-registered protocol; and **one** blind
run of the v3 test split, the current rules against the new ones.

## Commands

```bash
uv run verireview agreement dataset/annotations/claude/rw-v2.json dataset/annotations/jordan/rw-v2.json
uv run verireview build-gold dataset/annotations/jordan/rw-v2.json --single-source human
uv run verireview rescore-report experiments/phase10_1_test.json --out experiments/phase10_2_v2_rescored_human_labels.json
uv run verireview mine-candidates OWNER/REPO --max-prs 250 --out dataset/raw/candidates/v3/OWNER__REPO.jsonl
uv run verireview collect-cases FILES… --n 10 --seed 20261011 --test-fraction 1.0 --max-per-pull 3 --benchmark-version v3
uv run verireview annotation-sheet --batch rw-v3 --benchmark-version v3
uv run verireview annotation-sheet --batch rw-v3-shared --benchmark-version v3 --cases dataset/raw/sheets/rw-v3-shared.ids.txt
uv run verireview build-gold dataset/annotations/jordan/rw-v3.json --single-source human --benchmark-version v3
uv run verireview benchmark-freeze --benchmark-version v3
```

`rescore-report` scores against the labels of the report's own benchmark version (a v2 report
against the v2 labels), whatever the current version is.

## Limitations

- **One annotator, for v2 and for v3.** No adjudication, and no human–human agreement can be
  measured. The same person labelled both. The v1 real-world cases (dev data) still have
  provisional model labels.
- **Few bad real-world cases.** v3 has 5 not-satisfied and 2 partially satisfied real-world cases
  among 58, so a real-world false-acceptance rate will again rest on about 7 cases.
- **The authored test cases come from the rules' author** (written blind, same recipe).
- **The labelling page pre-selects "validation" and "satisfied"** for a new requirement, which can
  nudge an annotator. In the v3 export only 2 of 58 included cases sit at exactly those values, so
  there is no sign that defaults were left untouched, but the page should start empty next time.
- **Nothing was improved yet.** This phase changed labels and built the test set; the verifier's
  rules are those of Phase 10.1.
