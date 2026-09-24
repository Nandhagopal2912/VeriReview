# Phase 10: Evaluation and Ablation

**The test split of benchmark v1 was evaluated once**, with the pre-registered protocol
([phase10_protocol.md](phase10_protocol.md), sha256 `c78bfd7700e7…`, unchanged between the dev and
test runs). Commit `94a02113`, manifest v1, 2,000 bootstrap resamples, seed 20260924. Reports:
`experiments/phase10_test.json` and `experiments/phase10_dev.json`.

## Headline

**On data it had never seen, full VeriReview (F) is far weaker than its development numbers
suggested.**

| | Dev / held-out (seen while building the rules) | **Blind test (120 cases)** |
|---|---|---|
| Accuracy | 1.000 dev fixtures · 0.875 held-out | **0.483** [0.39, 0.57] |
| False acceptance (FAR) | 0.000 | **0.237** [0.14, 0.35] |
| False blocking (FBR) | 0.071 (held-out) | 0.196 [0.09, 0.31] |
| Real-world coverage | – | **0.000** (every case UNCERTAIN) |

The rules were developed and hardened on the dev fixtures and the held-out set (which lost its
blindness in Phase 5.1). The 100 new test cases were written blind, and the rules do not generalise
to them. This is the result the benchmark was built to find.

## Results (real output of `eval-benchmark --split test --final-test-run`)

```text
split test: 120 cases; commit 94a02113; manifest v1; protocol c78bfd7700e7; bootstrap 2000x seed 20260924

system accuracy [95% CI]       macro-F1 [95% CI]       FAR [95% CI]            FBR [95% CI]             coverage sel.acc
A      0.383 [0.29, 0.47]      0.168 [0.13, 0.21]      0.034 [0.00, 0.09]      0.922 [0.84, 0.98]          1.000   0.383
B      0.342 [0.25, 0.42]      0.148 [0.11, 0.19]      0.119 [0.05, 0.21]      0.941 [0.87, 1.00]          1.000   0.342
B'     0.508 [0.42, 0.60]      0.259 [0.21, 0.31]      0.797 [0.69, 0.89]      0.039 [0.00, 0.10]          1.000   0.508
L      0.442 [0.36, 0.53]      0.173 [0.14, 0.21]      0.966 [0.92, 1.00]      0.000 [0.00, 0.00]          1.000   0.442
S      0.542 [0.45, 0.63]      0.283 [0.23, 0.33]      0.763 [0.66, 0.87]      0.000 [0.00, 0.00]          1.000   0.542
R      0.500 [0.42, 0.59]      0.357 [0.27, 0.43]      0.712 [0.59, 0.82]      0.000 [0.00, 0.00]          0.850   0.539
C/D    0.483 [0.39, 0.57]      0.460 [0.35, 0.55]      0.237 [0.14, 0.35]      0.196 [0.09, 0.31]          0.667   0.625
E      0.483 [0.39, 0.57]      0.460 [0.35, 0.55]      0.237 [0.14, 0.35]      0.196 [0.09, 0.31]          0.667   0.625
F      0.483 [0.39, 0.57]      0.460 [0.35, 0.55]      0.237 [0.14, 0.35]      0.196 [0.09, 0.31]          0.667   0.625
F-gold 0.600 [0.51, 0.68]      0.600 [0.50, 0.69]      0.186 [0.10, 0.30]      0.294 [0.17, 0.43]          0.775   0.688

-- adversarial: n=40
system     acc    mF1    FAR    FBR    cov    sel
A        0.650  0.316  0.033  0.900  1.000  0.650
B        0.575  0.285  0.133  0.900  1.000  0.575
B'       0.450  0.316  0.733  0.000  1.000  0.450
L        0.250  0.133  1.000  0.000  1.000  0.250
S        0.500  0.352  0.667  0.000  1.000  0.500
R        0.475  0.339  0.667  0.000  0.975  0.487
C/D      0.550  0.464  0.267  0.500  0.925  0.595
E        0.550  0.464  0.267  0.500  0.925  0.595
F        0.550  0.464  0.267  0.500  0.925  0.595
F-gold   0.650  0.655  0.267  0.600  1.000  0.650

-- controlled: n=60
system     acc    mF1    FAR    FBR    cov    sel
A        0.267  0.133  0.040  0.920  1.000  0.267
B        0.233  0.109  0.120  0.960  1.000  0.233
B'       0.450  0.209  0.920  0.000  1.000  0.450
L        0.417  0.147  1.000  0.000  1.000  0.417
S        0.450  0.209  0.920  0.000  1.000  0.450
R        0.500  0.351  0.880  0.000  0.867  0.481
C/D      0.600  0.591  0.240  0.200  0.717  0.651
E        0.600  0.591  0.240  0.200  0.717  0.651
F        0.600  0.591  0.240  0.200  0.717  0.651
F-gold   0.750  0.749  0.120  0.240  0.817  0.755

-- real_world: n=20
system     acc    mF1    FAR    FBR    cov    sel
A        0.200  0.130  0.000  0.938  1.000  0.200
B        0.200  0.130  0.000  0.938  1.000  0.200
B'       0.800  0.482  0.500  0.125  1.000  0.800
L        0.900  0.580  0.500  0.000  1.000  0.900
S        0.900  0.580  0.500  0.000  1.000  0.900
R        0.550  0.507  0.000  0.000  0.550  1.000
C/D      0.000  0.000  0.000  0.000  0.000    n/a
E        0.000  0.000  0.000  0.000  0.000    n/a
F        0.000  0.000  0.000  0.000  0.000    n/a
F-gold   0.050  0.095  0.000  0.188  0.200  0.250

paired bootstrap, F minus X (95% CI):
  vs A       accuracy 0.100 [0.00, 0.20]           FAR 0.203 [0.11, 0.31]
  vs B       accuracy 0.142 [0.03, 0.25]           FAR 0.119 [-0.02, 0.26]
  vs B'      accuracy -0.025 [-0.17, 0.10]         FAR -0.559 [-0.69, -0.43]
  vs L       accuracy 0.042 [-0.11, 0.18]          FAR -0.729 [-0.83, -0.61]
  vs S       accuracy -0.058 [-0.19, 0.07]         FAR -0.525 [-0.65, -0.40]
  vs R       accuracy -0.017 [-0.13, 0.09]         FAR -0.475 [-0.60, -0.35]
  vs C/D     accuracy 0.000 [0.00, 0.00]           FAR 0.000 [0.00, 0.00]
  vs E       accuracy 0.000 [0.00, 0.00]           FAR 0.000 [0.00, 0.00]
  vs F-gold  accuracy -0.117 [-0.17, -0.07]        FAR 0.051 [-0.04, 0.14]

F confusion (rows gold, cols predicted: SAT PART NOT UNC):
  SATISFIED                17    1   10   23
  PARTIALLY_SATISFIED       5    5    2    3
  NOT_SATISFIED             9    1   28    6
  UNCERTAIN                 0    0    2    8
F accuracy by category:  api_behavior 0.50, error_handling 0.45, naming 0.73, other 0.00, testing 0.43, validation 0.65
F accuracy by confidence: LOW 0.20, MEDIUM 0.63
```

Similarity thresholds, all tuned on dev with Youden's J: A 0.917, B 0.712, B′ 0.02. They are near
degenerate: A and B accept almost nothing, B′ almost everything.

## Answers to the pre-registered questions

1. **Is F's FAR low, and lower than the similarity baselines'?** **No.** FAR 0.237 is lower than
   the permissive systems (B′ 0.80, L 0.97, S 0.76, R 0.71; paired differences all exclude 0), but
   *higher* than A (0.034; F − A = +0.20 [0.11, 0.31]) and not clearly different from B. A and B are
   safe only because they reject nearly everything (FBR 0.92–0.94).
2. **Does F beat the ablation rows?** **Only the text-similarity baselines.** F − A = +0.10
   [0.00, 0.20] and F − B = +0.14 [0.03, 0.25]. Against B′, L, S and R the accuracy intervals
   include 0. Rows C/D, E and F are identical by construction (ADR-002; Phase 8b was not done), so
   the semantic model changes nothing. Macro-F1 is F's clearest advantage (0.46 vs ≤ 0.36 for every
   non-F system), because it is the only one that uses all four verdicts.
3. **Real-world:** F abstains on all 20 cases (coverage 0). That is safe but useless there. The
   naive "something changed near the comment" systems (L, S) reach 0.90 accuracy on real-world,
   because 16 of those 20 threads were in fact addressed, while accepting half of the bad ones.

## Error analysis (descriptive only, nothing was changed)

**False acceptances (14 of 59 invalid resolutions):**

| Cause | Cases |
|---|---|
| Partial fix, second requirement missed (with gold requirements: 2 become correct, 1 UNCERTAIN) | 5: `c-naming-10`, `c-testing-09`, `c-testing-10`, `c-validation-09`, `a-testing-08` |
| Test exists but does not test the behaviour (no expectation, skipped, or only a pre-existing test with a different input) | 3: `a-testing-01`, `a-testing-02`, `a-testing-04` |
| Wrong value or condition accepted (inverted `if user:`, `< 0` for "at least 1", wrong exception caught) | 3: `c-api-08`, `a-validation-05`, `c-errors-06` |
| Handling that does not handle (`abort` after `return`, broad `except` kept, bare re-raise) | 3: `a-api-04`, `a-errors-05`, `a-errors-03` |

`a-testing-04` (a comment in the test file claiming the test exists) was **not** a successful
prompt injection. The explanation shows it was accepted through the "an existing test already
covers it" path (ADR-001), because `test_remove_some` calls the function. The testing rule does not
check that the existing test uses the requested input. The injected text played no role.

**False blocks (10 of 51 valid resolutions):** all are valid fixes in idioms the rules do not
recognise. Gold requirements do not fix any of them, so they are rule gaps:

| Idiom | Cases |
|---|---|
| status code as a Django `JsonResponse(status=400)`, a Flask `return …, 201`, `HTTPStatus.BAD_REQUEST`, a custom `@errorhandler` | 4 |
| `raise … from err`, `try/finally`, a Flask test client `status_code` assertion | 3 |
| validation in a dataclass `__post_init__` or a pydantic `Field(gt=0)` model; a rename that keeps a deprecated alias | 3 |

**Other findings:**
- **Extraction costs accuracy.** F-gold − F = +0.117 [0.07, 0.17], the only clear paired difference
  other than versus A and B.
- **Confidence is informative but not reliable enough to act on.** Accuracy is 0.63 at MEDIUM and
  0.20 at LOW. HIGH is never emitted, and MEDIUM is right only about two times in three. Blocking
  must stay off.
- **Per category (F, test):** naming 0.73, validation 0.65, api_behavior 0.50, error_handling
  0.45, testing 0.43, other 0.00.
- **By difficult-case type (F, controlled + adversarial test):**
  - 1.00: string mention, commented-out, misleading comment, wrong order, unrelated change;
  - 0.80: wrong target, prompt injection (the miss above is the testing rule);
  - 0.60: lexical false positive, dead code;
  - 0.40: partial;
  - 0.33: wrong value;
  - 0.14: unusual-but-valid idioms (false blocks);
  - 0.00: formatting-only (1 case).

## Limitations of this evaluation

- **Nobody independent labelled the data.** Controlled and adversarial labels come from the rules'
  author (written blind to the verifier). Real-world labels are provisional model labels (Claude).
  No inter-annotator agreement exists yet.
- **The samples are small:** 120 test cases, 20 real-world. Intervals are wide (±0.09 on accuracy).
- **The benchmark could be biased either way.** The adversarial set was built to break rules like
  these. The controlled set was written by someone who knew the rules' blind spots, which could make
  it too easy or too hard.
- This split is now **used**. Any rule change motivated by these errors has to be measured on a
  new test set (benchmark v2).

## Plan §29: research Definition of Done

| Item | Status |
|---|---|
| Real-world review examples collected | ✅ 50 (6 projects) |
| Human annotation protocol established | ✅ guide + tools; ⚠ no human labels yet |
| Ground-truth benchmark created | ✅ v1 frozen (real-world labels provisional) |
| Difficult / adversarial cases included | ✅ 40 |
| Baselines implemented | ✅ A, B, B′, L, S, R |
| Hybrid verifier implemented | ✅ E (semantic evidence neutral, ADR-002) |
| Per-class metrics, FAR, FBR measured | ✅ |
| Ablation study completed | ✅ with bootstrap and paired intervals |
| Calibration evaluated if numeric probabilities | n/a (no numeric probabilities; per-level accuracy reported) |
| Security model documented | ✅ [security_model.md](security_model.md) |
| Limitations documented | ✅ above and in the README |
| Reproducible experiments | ✅ one command per split; pinned commit, dataset hashes, seed |

## What this means next

1. **Advisory only.** Phase 11 (GitHub advisory mode) is reasonable: VeriReview's output is useful
   as a flag for human review, not as a gate. Enforcement (Phase 12) is not justified by these
   numbers.
2. **Largest gains, from the error analysis:**
   - partial-requirement handling and extraction;
   - testing rules that check the requested input and the expectation;
   - recognising common framework idioms (status codes, `try/finally`, `raise from`);
   - some story for `other` requests: 2/3 of real review comments, where F currently always
     abstains.
3. **Any such change needs benchmark v2** (new blind test cases, ideally human-labelled) to be
   evaluated honestly.

## Reproduce

```bash
uv run --group nlp verireview eval-benchmark --split dev --out experiments/phase10_dev.json
uv run --group nlp verireview eval-benchmark --split test --final-test-run --out experiments/phase10_test.json
```

Results are deterministic for a given commit and dataset (fixed seeds, pinned model revisions).
