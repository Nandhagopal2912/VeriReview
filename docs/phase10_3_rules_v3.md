# Phase 10.3: Rule Improvements, Evaluated Once on Benchmark v3

Phase 10.2 replaced the provisional real-world labels with one human annotator's labels, and froze
benchmark v3 before any rule changed. Phase 10.3 improves the rules on dev data only, mostly on
the v2 cases with human labels. It then runs the v3 test split **once**, old rules against new,
under a pre-registered protocol.

Order of work (recorded in `dataset/benchmark/v3/FREEZE_LOG.md`, entries 8–9):

1. **Change rules on dev only.** Dev has 345 cases: `fixtures`, `heldout_fixtures`, all of v1
   and v2.
2. **Pre-register the evaluation** ([phase10_3_protocol.md](phase10_3_protocol.md), sha256
   `e3e12c93436c…`). The rules were frozen at source hash `211a02c7d119…`.
3. **Run the v3 test split once**, for the old rules (commit `a71e55c`, the v3 freeze) and the
   new ones. Compare them paired, case by case.

## Headline

| v3 test, 148 cases | Phase 10.1 rules (F-old) | **Phase 10.3 rules (F)** | Paired difference F − F-old |
|---|---|---|---|
| Accuracy | 0.561 [0.48, 0.64] | **0.568** [0.49, 0.64] | +0.007 [0.00, +0.02] |
| False acceptance (FAR) | 0.105 [0.03, 0.19] | **0.088** [0.02, 0.17] | −0.018 [−0.06, 0.00] |
| False blocking (FBR) | 0.111 | 0.111 | 0.000 |
| Coverage | 0.581 | 0.568 | −0.014 [−0.03, 0.00] |
| Selective accuracy (right when decided) | 0.779 | 0.798 | |
| Real-world coverage (58, one annotator) | 0.224 | 0.224 | 0.000 |
| Real-world selective accuracy | 0.615 | 0.615 | |

**In plain words: the new rules changed only 2 of the 148 test cases.** Both had been accepted by
the old rules and are now "uncertain". For one (gold uncertain), that is now right. The other
(gold partially satisfied) is still wrong, but it is no longer a wrong acceptance, which is the
whole FAR change (6 → 5 of 57). Nothing broke. The fixes are real and safe, but they rarely fire on fresh
cases.

Answers to the pre-registered questions:

1. **Improvement: no.** Accuracy went up by 0.007 (one case), and the paired interval does not
   exclude 0 (lower bound 0.000).
2. **Safety: yes.** The paired FAR difference is −0.018, with upper bound 0.000. FAR did not go up.
3. **Real-world: no change.** Coverage is 0.224 and selective accuracy 0.615 for both the old and
   the new rules. Real-world FAR is 0 for both.
4. **Generalisation gap: larger.** Dev 0.771 against test 0.568 is a gap of 0.203; Phase 10.1's
   was 0.145 (dev 0.798 against test 0.653).

What this means: on dev the changes look good (11 cases fixed, 0 broken, FAR 0.061 → 0.007).
On fresh cases they almost never apply. Each fix targeted one specific pattern seen in dev, and
new cases bring new patterns. **VeriReview stays advisory only.** FAR on the test is 0.088 (5 wrong
acceptances out of 57 cases that should not be accepted), far from the ≤ 5% upper bound the
enforcement gate needs.

## What changed (all developed on dev data)

**Safety (wrong acceptances found in the v2 cases):**

- A check, handler or `with suppress(...)` after an unconditional `return`/`raise` never runs, so
  it does not count (`rules/analysis.py`).
- `HTTPException(404)` written as a statement (not raised, not returned) does nothing, so it does
  not count. `abort(404)` still does.
- Validation (`rules/validation.py`):
  - **Polarity.** A range check must reject what the request rejects. For "not negative",
    `if limit >= 0: raise` is the wrong way round. The condition is evaluated on sample values
    from the request with Python's `ast`, without running anything. A condition that cannot be
    evaluated is not second-guessed.
  - **Flags.** A check behind an unrelated flag (`if DEBUG and source is target`) is not
    satisfied when the flag is a module constant `False`, and inconclusive when the flag's value
    is unknown.
  - "are dates", "is a list" ask for a type check.
- Error handling: "`open()` raises …; handle that" means the `open()` call itself must be
  protected (`rules/errors.py`).
- Testing (`rules/testing.py`):
  - A new test in a file that pytest/unittest do not collect by default (`tests/port_checks.py`)
    is inconclusive.
  - A scenario described only in words ("a test for a birthday in the future") must be
    mentioned by the test. Otherwise the result is inconclusive. Words from the function's own
    name and parameters do not count as a scenario.
- Extraction: "more gracefully" (any "more …ly", or "gracefully") with no code target is ambiguous
  (`requirements/lexicon.py`). The protocol's summary also lists "properly", which is wrong. The
  pattern does not include it. The code is what the source hash pins.

**Coverage (real-world dev cases with no rule):**

- A comment with no other request that calls the commented code superfluous is a removal
  request: "No longer used", "can be left out", "duplicates the line above". It is checked by the
  existing removal rule. A bare "is not used" is left out, because it may mean "use it".
- "add `# GH#63221`": an exact comment given in backticks must now be in the file
  (`rules/other.py`).

Pipelines are now `mvp-3` / `phase5-rules-3` / `phase7-semantic-3`. Each new check has positive,
negative and adversarial tests (`tests/rules/test_rules_v3.py`, `tests/unit/requirements/
test_extraction.py`). Each new check has at least one test that fails on the old rules. This was
verified by running the tests against the `git archive a71e55c` export: 20 fail there, all pass
now.

### Checks on dev (before the test run)

| Check | Before (commit a71e55c) | After |
|---|---|---|
| Dev split F (345) | acc 0.739, FAR 0.061, FBR 0.018, coverage 0.704 | acc 0.771, FAR 0.007, FBR 0.018, coverage 0.707 |
| Cases changed on dev | | 11 fixed, 0 broken, 2 still wrong but changed (S → U, gold N) |
| Dev fixtures (29) | 1.000, FAR 0 | 1.000, FAR 0 |
| Held-out verdict fixtures (24) | 0.917, FAR 0, FBR 0.071 | 0.917, FAR 0, FBR 0.071 (identical) |
| Held-out requirements (32) | count 0.938, category F1 0.974 | unchanged |
| Prompt injection | 0 changes | 0/708 (`mvp`), 0/708 (`phase7-semantic`) |
| Unit + benchmark tests | | 1264 passed; integration 39 passed |

## Results

### Phase 10.1 rules on v3 test (real output, protocol step 2)

```text
split test: 148 cases; commit a71e55cd; manifest v3; protocol e3e12c93436c; bootstrap 2000x seed 20260924

system accuracy [95% CI]       macro-F1 [95% CI]       FAR [95% CI]            FBR [95% CI]             coverage sel.acc
F      0.561 [0.48, 0.64]      0.596 [0.51, 0.67]      0.105 [0.03, 0.19]      0.111 [0.04, 0.19]          0.581   0.779
F-gold 0.608 [0.53, 0.68]      0.635 [0.55, 0.70]      0.053 [0.00, 0.12]      0.153 [0.07, 0.24]          0.615   0.802

-- adversarial: n=30
system     acc    mF1    FAR    FBR    cov    sel
F        0.867  0.802  0.040  0.600  1.000  0.867
F-gold   0.867  0.802  0.040  0.600  1.000  0.867

-- controlled: n=60
system     acc    mF1    FAR    FBR    cov    sel
F        0.683  0.679  0.200  0.040  0.717  0.767
F-gold   0.800  0.777  0.080  0.080  0.783  0.851

-- real_world: n=58
system     acc    mF1    FAR    FBR    cov    sel
F        0.276  0.194  0.000  0.095  0.224  0.615
F-gold   0.276  0.210  0.000  0.143  0.241  0.500
```

### Phase 10.3 rules and the ablation on v3 test (real output, protocol step 3)

```text
split test: 148 cases; commit a71e55cd; manifest v3; protocol e3e12c93436c; bootstrap 2000x seed 20260924

system accuracy [95% CI]       macro-F1 [95% CI]       FAR [95% CI]            FBR [95% CI]             coverage sel.acc
A      0.318 [0.24, 0.39]      0.158 [0.12, 0.20]      0.018 [0.00, 0.06]      0.889 [0.81, 0.96]          1.000   0.318
B      0.304 [0.23, 0.38]      0.142 [0.11, 0.18]      0.000 [0.00, 0.00]      0.931 [0.87, 0.99]          1.000   0.304
B'     0.507 [0.43, 0.59]      0.245 [0.20, 0.29]      0.825 [0.72, 0.92]      0.097 [0.03, 0.17]          1.000   0.507
L      0.480 [0.40, 0.56]      0.174 [0.15, 0.21]      0.982 [0.94, 1.00]      0.014 [0.00, 0.05]          0.993   0.483
S      0.561 [0.48, 0.64]      0.302 [0.26, 0.35]      0.702 [0.58, 0.81]      0.069 [0.01, 0.13]          0.993   0.565
R      0.480 [0.40, 0.56]      0.368 [0.30, 0.43]      0.614 [0.48, 0.74]      0.042 [0.00, 0.10]          0.703   0.567
C/D    0.568 [0.49, 0.64]      0.602 [0.52, 0.67]      0.088 [0.02, 0.17]      0.111 [0.04, 0.19]          0.568   0.798
E      0.568 [0.49, 0.64]      0.602 [0.52, 0.67]      0.088 [0.02, 0.17]      0.111 [0.04, 0.19]          0.568   0.798
F      0.568 [0.49, 0.64]      0.602 [0.52, 0.67]      0.088 [0.02, 0.17]      0.111 [0.04, 0.19]          0.568   0.798
F-gold 0.608 [0.53, 0.68]      0.635 [0.55, 0.70]      0.053 [0.00, 0.12]      0.153 [0.07, 0.24]          0.615   0.802

-- real_world: n=58
system     acc    mF1    FAR    FBR    cov    sel
A        0.190  0.106  0.000  0.857  1.000  0.190
B        0.172  0.096  0.000  0.881  1.000  0.172
B'       0.638  0.258  0.714  0.167  1.000  0.638
L        0.707  0.271  0.857  0.024  0.983  0.719
S        0.655  0.275  0.714  0.119  0.983  0.667
R        0.397  0.255  0.000  0.071  0.397  0.739
C/D      0.276  0.194  0.000  0.095  0.224  0.615
E        0.276  0.194  0.000  0.095  0.224  0.615
F        0.276  0.194  0.000  0.095  0.224  0.615
F-gold   0.276  0.210  0.000  0.143  0.241  0.500

paired bootstrap, F minus X (95% CI):
  vs A       accuracy 0.250 [0.16, 0.34]           FAR 0.070 [0.00, 0.16]
  vs B       accuracy 0.264 [0.18, 0.35]           FAR 0.088 [0.02, 0.17]
  vs B'      accuracy 0.061 [-0.07, 0.19]          FAR -0.737 [-0.85, -0.62]
  vs L       accuracy 0.088 [-0.04, 0.22]          FAR -0.895 [-0.97, -0.82]
  vs S       accuracy 0.007 [-0.12, 0.14]          FAR -0.614 [-0.74, -0.48]
  vs R       accuracy 0.088 [-0.01, 0.19]          FAR -0.526 [-0.66, -0.40]
  vs C/D     accuracy 0.000 [0.00, 0.00]           FAR 0.000 [0.00, 0.00]
  vs E       accuracy 0.000 [0.00, 0.00]           FAR 0.000 [0.00, 0.00]
  vs F-gold  accuracy -0.041 [-0.10, 0.01]         FAR 0.035 [0.00, 0.09]

F confusion (rows gold, cols predicted: SAT PART NOT UNC):
  SATISFIED                25    0    8   39
  PARTIALLY_SATISFIED       1   10    2    4
  NOT_SATISFIED             4    0   32    4
  UNCERTAIN                 1    0    1   17
F accuracy by category:  api_behavior 0.48, error_handling 0.70, naming 0.84, other 0.44, testing 0.48, validation 0.62
F accuracy by confidence: LOW 0.26, MEDIUM 0.82
```

(The controlled and adversarial per-system tables are in `experiments/phase10_3_test.json`.)

### Old against new, paired (real output, protocol step 4)

```text
F: experiments\phase10_3_test.json minus experiments\phase10_3_test_old_rules.json (paired bootstrap 2000x, 148 cases)
  pooled       n=148  acc +0.007 [+0.00, +0.02]  FAR -0.018 [-0.06, +0.00]  FBR +0.000 [+0.00, +0.00]  cov -0.014 [-0.03, +0.00]
  adversarial  n= 30  acc +0.000 [+0.00, +0.00]  FAR +0.000 [+0.00, +0.00]  FBR +0.000 [+0.00, +0.00]  cov +0.000 [+0.00, +0.00]
  controlled   n= 60  acc +0.017 [+0.00, +0.05]  FAR -0.040 [-0.13, +0.00]  FBR +0.000 [+0.00, +0.00]  cov -0.033 [-0.08, +0.00]
  real_world   n= 58  acc +0.000 [+0.00, +0.00]  FAR +0.000 [+0.00, +0.00]  FBR +0.000 [+0.00, +0.00]  cov +0.000 [+0.00, +0.00]
```

F-gold: all differences are 0.000 (`experiments/phase10_3_test_paired_gold.json`).

The two cases that changed:

| Case | Gold | Old | New | Why |
|---|---|---|---|---|
| `v3c-testing-11-coverage-is-thin` | uncertain | satisfied | **uncertain** (fixed) | the scenario named in words is not shown by the test |
| `v3c-testing-10-retry-tested-count-fixed` | partial | satisfied | uncertain (still wrong) | the same check |

## Reading the results

- **The new rules are safe but narrow.** No case got worse. Both changed cases were caught by the
  same new check (the test scenario). None of the other new checks fired on
  any of the 148 fresh cases.
- **Real-world: nothing changed.** The v3 real-world requests did not contain the patterns added
  for coverage (removal statements, literal comments). 31 of the 58 are satisfied requests the
  system leaves uncertain, mostly `other` requests with no rule. Real-world FAR is 0: of the
  5 not-satisfied requests, none was accepted.
- **Rules versus baselines.** On real-world, the similarity baselines (L, S, B′) have higher
  accuracy (0.64–0.71), but only because they accept almost everything, and 42 of the 58 are
  satisfied. Their FAR is 0.71–0.86. F accepts nothing it should not, but decides only 22% of
  real-world cases.
- **Enforcement gate: still no category eligible.** `verireview enforcement-eligibility
  experiments/phase10_3_test.json` (read-only, not `--write`) gives upper bounds of 0.22–0.78 for
  FAR, against the 0.05 the gate needs. The shipped `eligibility.json` is unchanged; regenerating
  it is the owner's decision.
- **The dev–test gap grew (0.145 → 0.203).** Rules fixed one at a time on dev cases do not carry
  over to new cases well. This is the main lesson of this phase.

## Error analysis on v3 test (descriptive, after the single run)

These are reproduced with the same code as the run; nothing here has changed the rules. Fixes
belong to a later phase with a v4 test set frozen first.

**Wrong acceptances (5, plus 1 uncertain case accepted):**

- `v3c-errors-06`: "Raise `ValueError` …, not `KeyError`". Extraction made it a validation request,
  and a `KeyError` check counted. The "not X" part was lost.
- `v3c-naming-07`: a rename done in one function but not in another function of the same module
  ("in this module"). The naming rule only looks at the commented function.
- `v3c-naming-10`: "rename … and make it return a bool". The second request was also routed to
  naming, and the rename satisfied both.
- `v3c-testing-07`: "a test for an expired token". The new test mentions "expires", but with a
  future time. The scenario check matches words, not meaning.
- `v3a-validation-02`: a check nested under `if TYPE_CHECKING:` (false at run time). The flag
  check only looks at `and` in the same condition, not at an enclosing `if`.
- `encode__httpx__1522__599878626` (gold uncertain): a suggestion applied exactly. The annotator
  judged it uncertain because other files were not changed the same way.

**Wrong blocks (8):**

- Unusual idioms (adversarial, by design): `contextlib.suppress` plus a later `return ''`;
  `pytest.raises(ValueError, chunk, …)` (callable form); a clamp comparison
  (`if ratio != min(max(ratio, 0), 1): raise`).
- `v3c-api-02`: "Respond with 201 when a note is created". The rule wanted 201 on a branch.
- Real-world:
  - Two requests about f-strings and lazy translation were wrongly categorised as validation.
  - A suggestion applied in a different style (`typing.AsyncIterable` instead of a new import).
  - A request for tests of the commented test function itself.

**Not decided (uncertain while gold is satisfied: 39, of which 31 real-world):** mostly `other`
requests with no rule, as in Phase 10.1.

## Limitations

- Same author: the v3 controlled and adversarial cases were written by the same author as the
  rules (before these changes, from the v2 recipe). The real-world cases are the independent part.
- Real-world labels come from **one human annotator**, not adjudicated, with no human–human kappa.
- Only 5 real-world test cases are not satisfied, so real-world FAR rests on very few cases.
- A single run: the only variance measured is over cases.
- The v3 test split has now been looked at. It is dev data for any further rule change, which
  needs a v4 test set frozen first.

## Reproduce

```bash
# dev (any time)
uv run verireview eval-benchmark --split dev --systems F,F-gold --no-models --out experiments/phase10_3_dev.json
# the recorded test runs (same code only; never to try variants)
git archive a71e55c src | tar -x -C /tmp/old && PYTHONPATH=/tmp/old/src uv run verireview eval-benchmark --split test --final-test-run --systems F,F-gold --no-models --protocol docs/phase10_3_protocol.md --out experiments/phase10_3_test_old_rules.json
HF_HUB_OFFLINE=1 uv run --group nlp verireview eval-benchmark --split test --final-test-run --protocol docs/phase10_3_protocol.md --out experiments/phase10_3_test.json
uv run verireview compare-reports experiments/phase10_3_test_old_rules.json experiments/phase10_3_test.json --system F
```
