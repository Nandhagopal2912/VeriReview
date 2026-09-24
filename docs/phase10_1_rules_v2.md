# Phase 10.1: Rule Improvements, Evaluated on a New Blind Benchmark (v2)

Phase 10 showed that the rules did not generalise: accuracy 0.483 and FAR 0.237 on the blind v1
test split, and 0 coverage on real-world requests. Phase 10.1 fixes the causes found in that error
analysis, and measures the fixes on a **new** test set that was frozen before any rule changed.
The v1 test split had been looked at, so it became development data.

Order of work (recorded in `dataset/benchmark/v2/FREEZE_LOG.md`):

1. **Freeze v2 first.** 60 controlled and 30 adversarial cases were written blind from the v1
   recipe. 60 fresh real-world threads were collected (10 per approved repo, from PRs not used in
   v1) and labelled blind by Claude (provisional, `label_source: model`); 57 are included. All of
   this is hashed and pinned (`dataset/benchmark/v2/manifest.json`,
   `tests/benchmark/test_benchmark_v2.py`).
2. **Change rules on dev only.** Dev is `fixtures`, `heldout_fixtures` and all of v1: 203 cases.
3. **Pre-register the evaluation** ([phase10_1_protocol.md](phase10_1_protocol.md), sha256
   `e3a7f5e68d6e…`). The rules were frozen at source hash `287fca5e…`.
4. **Run the v2 test split once**, for the old rules (Phase 10 code, commit `1b530fa`) and the
   new ones. Compare them paired, case by case.

## Headline

| v2 test, 147 cases | Phase 10 rules (F-old) | **Phase 10.1 rules (F)** | Paired difference F − F-old |
|---|---|---|---|
| Accuracy | 0.422 [0.34, 0.50] | **0.653** [0.58, 0.73] | **+0.231** [+0.16, +0.31] |
| False acceptance (FAR) | 0.302 [0.18, 0.43] | **0.151** [0.06, 0.26] | **−0.151** [−0.25, −0.07] |
| False blocking (FBR) | 0.100 | **0.037** | −0.062 [−0.12, −0.01] |
| Coverage | 0.551 | **0.680** | +0.129 [+0.07, +0.19] |
| Real-world coverage (57) | 0.088 | **0.439** | +0.351 [+0.21, +0.49] |
| Real-world selective accuracy | 0.400 | **0.920** | |

Both pre-registered primary questions are answered yes. Accuracy rose, and the paired interval
excludes 0. FAR fell, which is stricter than the "not higher" that was required. The gap between
dev and test shrank from about 0.4–0.5 in Phase 10 (dev 1.0 / held-out 0.875 against test 0.483)
to 0.145 (dev 0.798 against test 0.653).

FAR is still 0.151, not 0. **VeriReview remains advisory only.** Eight decided cases on the new
test set were accepted when they should not have been (see the error analysis below).

## What changed (all developed on dev data)

**Requirement extraction** (`requirements/extraction.py`, `lexicon.py`):

- Category cues:
  - "log", "ignore", "close/release", "even if" → error handling.
  - "call it `x`" and "something like `x` would be better" → naming.
  - "cover", "we need a test" → testing.
  - "is actually a number" and "reject it" → validation.
  - "return X instead of Y" → API behaviour.
  - Documentation requests → `other`.
  - "docstring please." counts as a request.
- Each clause keeps its own category. Before, "…, and log the timeout" inherited *testing*.
- New splits:
  - "…, and that `start <= end`" becomes a requirement of its own.
  - "400 for X and 422 for Y" becomes two requirements.
  - "Handle E: log it and re-raise" drops the header.
  - "catch E and return Y" stays one requirement.
- Extraction scores:
  - On 153 dev benchmark cases: count 0.941 → 0.987, category 0.817 → 0.961.
  - Held-out requirement set: unchanged (0.938 / 0.974).

**Testing rule**:

- A new test must:
  - run: not skipped or xfailed;
  - assert something;
  - expect the requested exception (`pytest.raises` / `assertRaises`);
  - be new: a renamed test is not new.
- "single item" needs a one-element collection.
- Sibling test requirements cannot share one test unless each names its own scenario.
- A web handler can be tested through the test client by URL.
- A test that goes through a fixture defined elsewhere is inconclusive.
- The ADR-001 "existing test covers it" path now needs a checkable case.

**Error-handling rule**:

- Catching:
  - "`x` raises E; handle that" means catch E.
  - A handler that only re-raises handles nothing.
  - A handler must protect the call the comment names.
  - "catch only E" fails if a broad `except Exception` remains.
  - `contextlib.suppress` counts as a way to ignore.
- Raising and logging:
  - `raise … from err` counts as chaining.
  - "log it with the traceback" needs `logger.exception` or `exc_info`.
- "Don't swallow it" is a check of its own.
- "Make sure it gets closed / released even if…" needs a `finally` or `with`.
- A `with helper():` defined elsewhere is inconclusive.
- "an empty dict" means `{}`.

**API rule**:

- Status sources:
  - Status names: `HTTPStatus.*`, `status.HTTP_4xx_*`, Django response classes.
  - Raised HTTP exceptions (`Http404`, `NotFound`), and custom ones an `@app.errorhandler` maps
    to a status.
- Branches:
  - An `except` clause is a branch.
  - Code after `return` is unreachable.
  - "when X is not found" needs an absent-X branch: `if user:` returning 404 is wrong.
- A request without a condition ("creating a note should return 201") needs no branch.
- "not a 500" marks 500 as the unwanted status.
- New checks: "include the id in the error message" (interpolated values only), and "return []
  instead of None".

**Validation rule**:

- Range checks use the requested bound: "at least 1" is not `x < 0`, and "positive" rejects 0.
- Plural words find their singular variable: "ages" → `age`.
- A `__post_init__` check is not "too late" for the field it guards.
- A pydantic model built from the value counts as a delegated check: `Field(gt=0)`, constrained
  types, or `@field_validator`.

**Naming rule**: a compatibility alias (`get_user = fetch_user`) no longer undoes a rename.

**New `other` rules and suggestion blocks** (`rules/other.py`):

- A GitHub ```suggestion block is checked line by line inside the commented function, allowing
  for whitespace and formatter reflow. The outcome is:
  - applied: satisfied;
  - commented lines untouched and the suggestion absent: not satisfied;
  - changed some other way: inconclusive.
  An empty suggestion means "delete these lines". A suggestion's result is final: an undecided
  suggestion is not second-guessed by, for example, the naming rule.
- "Remove / drop this (comment, line, …)" and "remove `x`".
- "Add a docstring".
- "Use `A` instead of `B`".

Every new check has positive, negative and adversarial tests in `tests/rules/*_v2.py` and
`tests/rules/test_other_rule.py`, 1,030 unit tests in all. Pipelines were renamed to `mvp-2`,
`phase5-rules-2` and `phase7-semantic-2`. The safety pins still hold:

- dev fixtures 29/29;
- held-out fixtures 0.917, up from 0.875, with FAR still 0;
- **0 outcome changes in the prompt-injection suite** (1,288 variants per verifier: 708 dev +
  580 held-out, for `mvp` and `phase7-semantic`);
- `phase7-semantic` verdicts identical to `mvp`.

## Results

### Phase 10 rules on v2 test (real output, protocol step 2)

```text
split test: 147 cases; commit unknown; manifest None; protocol c78bfd7700e7; bootstrap 2000x seed 20260924

system accuracy [95% CI]       macro-F1 [95% CI]       FAR [95% CI]            FBR [95% CI]             coverage sel.acc
F      0.422 [0.34, 0.50]      0.456 [0.36, 0.54]      0.302 [0.18, 0.43]      0.100 [0.04, 0.17]          0.551   0.617
F-gold 0.456 [0.37, 0.54]      0.511 [0.42, 0.59]      0.302 [0.18, 0.43]      0.263 [0.16, 0.36]          0.639   0.585
```

"commit unknown / manifest None / protocol c78bfd7700e7": the Phase 10 code ran from a
`git archive` export of commit `1b530fa`. Its v1-only layout read the v2 test sets from a copy,
and it records its own (Phase 10) protocol file.

### Phase 10.1 rules and the ablation on v2 test (real output, protocol step 3)

```text
split test: 147 cases; commit 1b530fae; manifest v2; protocol e3a7f5e68d6e; bootstrap 2000x seed 20260924

system accuracy [95% CI]       macro-F1 [95% CI]       FAR [95% CI]            FBR [95% CI]             coverage sel.acc
A      0.320 [0.24, 0.40]      0.161 [0.12, 0.20]      0.019 [0.00, 0.06]      0.875 [0.79, 0.94]          1.000   0.320
B      0.279 [0.21, 0.35]      0.122 [0.09, 0.16]      0.000 [0.00, 0.00]      0.963 [0.91, 1.00]          1.000   0.279
B'     0.565 [0.49, 0.64]      0.259 [0.21, 0.31]      0.830 [0.72, 0.93]      0.075 [0.03, 0.14]          1.000   0.565
L      0.551 [0.47, 0.63]      0.190 [0.16, 0.22]      0.981 [0.94, 1.00]      0.000 [0.00, 0.00]          1.000   0.551
S      0.612 [0.53, 0.69]      0.292 [0.24, 0.34]      0.792 [0.67, 0.90]      0.013 [0.00, 0.04]          1.000   0.612
R      0.497 [0.41, 0.58]      0.330 [0.26, 0.40]      0.792 [0.67, 0.90]      0.013 [0.00, 0.04]          0.789   0.569
C/D    0.653 [0.58, 0.73]      0.655 [0.56, 0.73]      0.151 [0.06, 0.26]      0.037 [0.00, 0.08]          0.680   0.840
E      0.653 [0.58, 0.73]      0.655 [0.56, 0.73]      0.151 [0.06, 0.26]      0.037 [0.00, 0.08]          0.680   0.840
F      0.653 [0.58, 0.73]      0.655 [0.56, 0.73]      0.151 [0.06, 0.26]      0.037 [0.00, 0.08]          0.680   0.840
F-gold 0.592 [0.52, 0.67]      0.621 [0.53, 0.70]      0.170 [0.08, 0.28]      0.163 [0.09, 0.24]          0.667   0.755

-- adversarial: n=30
F        0.767  0.721  0.200  0.200  1.000  0.767
-- controlled: n=60
F        0.783  0.775  0.120  0.040  0.750  0.844
-- real_world: n=57
F        0.456  0.443  0.000  0.020  0.439  0.920

paired bootstrap, F minus X (95% CI):
  vs A       accuracy 0.333 [0.24, 0.43]           FAR 0.132 [0.04, 0.24]
  vs B       accuracy 0.374 [0.28, 0.47]           FAR 0.151 [0.06, 0.26]
  vs B'      accuracy 0.088 [-0.03, 0.20]          FAR -0.679 [-0.80, -0.55]
  vs L       accuracy 0.102 [-0.02, 0.22]          FAR -0.830 [-0.92, -0.72]
  vs S       accuracy 0.041 [-0.07, 0.16]          FAR -0.642 [-0.77, -0.51]
  vs R       accuracy 0.156 [0.07, 0.24]           FAR -0.642 [-0.77, -0.51]
  vs F-gold  accuracy 0.061 [-0.01, 0.14]          FAR -0.019 [-0.06, 0.00]

F confusion (rows gold, cols predicted: SAT PART NOT UNC):
  SATISFIED                44    0    3   33
  PARTIALLY_SATISFIED       2    9    3    1
  NOT_SATISFIED             6    0   31    1
  UNCERTAIN                 1    0    1   12
F accuracy by category:  api_behavior 0.72, error_handling 0.57, naming 0.82, other 0.55, testing 0.61, validation 0.78
F accuracy by confidence: LOW 0.36, MEDIUM 0.84
```

(The per-source tables are cut to the F rows here. The full output is in
`experiments/phase10_1_test.json`.)

### Old against new, paired (real output, protocol step 4)

```text
F: experiments\phase10_1_test.json minus experiments\phase10_1_test_old_rules.json (paired bootstrap 2000x, 147 cases)
  pooled       n=147  acc +0.231 [+0.16, +0.31]  FAR -0.151 [-0.25, -0.07]  FBR -0.062 [-0.12, -0.01]  cov +0.129 [+0.07, +0.19]
  adversarial  n= 30  acc +0.200 [+0.03, +0.37]  FAR -0.160 [-0.31, -0.04]  FBR -0.400 [-1.00, +0.00]  cov +0.000 [+0.00, +0.00]
  controlled   n= 60  acc +0.133 [+0.05, +0.23]  FAR -0.160 [-0.32, -0.04]  FBR -0.040 [-0.14, +0.00]  cov -0.017 [-0.07, +0.03]
  real_world   n= 57  acc +0.351 [+0.21, +0.49]  FAR +0.000 [+0.00, +0.00]  FBR -0.040 [-0.10, +0.00]  cov +0.351 [+0.21, +0.49]
```

The paired difference for F-gold is +0.136 [+0.08, +0.20] in accuracy and −0.132 in FAR
(`experiments/phase10_1_test_paired_gold.json`).

## Reading the results

- **The improvement holds on every source.** It is clearest on real-world requests, where
  coverage rose from 5 to 25 of 57 cases. 23 of those 25 decisions are correct, and none is a
  false acceptance. 24 of the 25 come from the suggestion-block check; free-text real-world
  requests are still almost always left to a human.
- **F now beats every structural and code-model baseline on FAR by a wide margin.** On accuracy
  it beats A, B and R clearly; against S, L and B′ the intervals include 0. Those baselines score
  well on real-world accuracy (0.79–0.90) only because most real-world gold is SATISFIED and they
  accept almost everything: their FAR is 0.67.
- **F-gold is now below F** (0.592 against 0.653). In Phase 10 it was above (0.600 against
  0.483). Gold requirement descriptions are paraphrases written by the annotator, and the rules
  now read the reviewer's own words more closely ("call it `x`", "not a 500"). This is
  descriptive only; it says extraction is no longer the main bottleneck.
- **Abstention works as intended:** MEDIUM-confidence verdicts are right 84% of the time, LOW
  ones 36%.

## Error analysis on v2 test (descriptive, after the single run)

**False acceptances (8).** Each is a gap the rules do not model yet:

| Case | Why it was accepted |
|---|---|
| `v2a-errors-03-handler-after-return` | the handler sits in unreachable code; the dead-code check covers statuses, not handlers |
| `v2a-api-02-exception-not-raised` | a 404 exception is built but never raised |
| `v2a-testing-02-not-collected-file` | the new test lives in a file pytest would not collect |
| `v2a-validation-02-inverted-condition` | the guard rejects valid values (`if limit >= 0: raise`); validation has no polarity check |
| `v2a-validation-06-second-check-debug-only` | the second check only runs in debug mode |
| `v2c-errors-08-wrong-statement` | the handler protects another statement; `open()` has no module prefix, so the protected-call check does not apply |
| `v2c-testing-07-normal-input-only` | "a birthday in the future" has no case word; a test with normal input passes |
| `v2c-validation-10-order-not-type` | "and that both are dates": "both" is not resolved to `start` and `end` |

**Other decided errors (8 of the 16 wrong decisions):**

- **Extraction did not split:**
  - "401 without a token and 403 for non-admins" (the split needs "for / when / if"), in
    `v2c-api-09`.
  - "404 with an error message when …" was kept as one requirement, in `v2c-api-10`. Both are
    partial cases judged not satisfied.
- **Read wrongly:**
  - "Don't use a bare `except`; catch `OSError`": the generic "handling" check failed on a
    changed handler (`v2c-errors-05`).
  - "Wrap `JSONDecodeError` in `SettingsError` and chain": `SettingsError` was treated as an
    exception to catch (`v2a-errors-01`).
- **Idiom:** `@validate_call` with `Annotated[..., Field(ge=0)]` is not recognised
  (`v2a-validation-05`).
- **Vague request answered:** "handle failures more gracefully" should stay UNCERTAIN
  (`v2c-errors-11`).
- **Real-world, pandas:** the commented file *is* the test file, so its test changes are not seen
  as test changes.
- **Real-world, blank-line suggestion:** an empty suggestion on a blank line was judged "not
  deleted"; the label is uncertain.

**Uncertain (47 of 147):** mostly real-world. 23 cases are held back by the ambiguity gate
(questions and hedges). About 22 requests have no general rule: "move this into X", "simplify",
"make this a fixture", and so on. Abstaining here is by design; the answer goes to human review.

These findings are **not fixed in this phase**. Fixing them would tune against v2 test. They
belong to a later phase with a v3 test set, and v2 becomes dev data then.

## Limitations

- **v2 was written by the rule author.** v2 `controlled` and `adversarial` were written by the same
  author as the rules, after the v1 error analysis. The recipe was kept identical to v1, but
  targeting cannot be ruled out. The fresh real-world cases are the independent part, and their
  labels are provisional (one model annotator, blind).
- **One run, one rule version.** The intervals capture case sampling only.
- **Not a gating tool.** FAR 0.15 is far from what blocking a merge would need. The BLOCK policy
  stays disabled, and HIGH confidence is never emitted.

## Reproduce

```bash
uv run verireview benchmark-stats --benchmark-version v2
uv run --group nlp verireview eval-benchmark --split dev --benchmark-version v2 --protocol docs/phase10_1_protocol.md
uv run verireview compare-reports experiments/phase10_1_test_old_rules.json experiments/phase10_1_test.json --system F
```

Re-running `--split test --final-test-run` on the same code and data reproduces the recorded
numbers. It must not be used to try variants.
