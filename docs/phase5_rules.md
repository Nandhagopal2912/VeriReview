# Phase 5: Deterministic Rule Engine

**Goal (roadmap):** explicit, testable verification rules for the five MVP categories. Each one
returns *satisfied / not satisfied / inconclusive* for one requirement, with evidence.

## Architecture

```text
ReviewRequirement (Phase 4) ──► for each requirement: RULES[category](requirement, RuleContext)
                                     │  structural queries (rules/analysis.py, Tree-sitter):
                                     │  guards · handlers · responses · test functions
                                     ▼
                               RuleOutcome(status, summary, evidence, already_present)
                                     ▼
            evidence/rules.py: rule evidence + one `rule_result` per requirement
                                     ▼
            verification/rules.py: per-requirement status → overall verdict (behind the ambiguity gate)
```

`RuleContext` holds the resolved target function before/after (Phase 3 location resolution,
including code moved into a helper), both whole files, and the test files before/after
(`ReviewCase.test_files_before`, new in schema v3).

## Rules

| Rule | Satisfied when (all structural, never raw text) | Adversarial cases it rejects |
|---|---|---|
| **Naming** | old identifier gone from its scope (file-wide for functions/classes); demanded new name used ("to `x`"), or any new name if only an example ("like `x`") | a comment mentioning the new name; renamed to a different name; callers not updated; another requirement's rename |
| **Validation** | a guard on the *requested* variable, of the requested kind (None / empty / range / type), whose branch raises/returns/asserts, before the commented operation | check on another variable; check after the write; check that only logs; docstring mentioning validation; wrong kind (range asked for type) |
| **Testing** | a new/changed test that calls the function under test and feeds the requested case (empty, blank, None, negative, zero, timeout, stated numbers) in its body | test *named* for the case but not exercising it; test for another function; renamed existing test |
| **Error handling** | a checklist from the request: catch E (not by swallowing), retry, raise F, log (with named values), re-raise, fall back to X; or, generically, a new handler/guard | `except Exception: pass`; log without the requested values; single attempt when retry asked |
| **API behaviour** | the requested status (ignoring "not 200", "instead of 400", "right now a 500") returned or aborted with, on a branch conditioned on the requested values; headers by name | status only in a comment; wrong status on the branch (named explicitly); status on the `else` branch |

**ADR-001:** every rule reports `already_present` when the satisfying construct existed before the
comment. The verdict is SATISFIED, capped at MEDIUM.

**Aggregation:** everything satisfied → SATISFIED. Some satisfied and some not → PARTIALLY_SATISFIED.
Some not and none satisfied → NOT_SATISFIED. Anything inconclusive (and nothing not satisfied) → UNCERTAIN.
Confidence is MEDIUM, or LOW if anything was inconclusive. It is never HIGH before calibration (Phase 10).

## Evaluation protocol

1. **Dev fixtures (29):** the rules were designed while looking at these, so the numbers are
   training numbers.
2. **Held-out verdict fixtures (24)** in `dataset/heldout_fixtures/`: written **after** the rules
   were frozen, labelled by reviewer judgement (not by predicted behaviour), deliberately
   including idioms the rules might not know. Hashed (`d5a64d31…`, pinned in a benchmark test)
   and run **once**. No rule was changed in response.
3. Both are run twice: with **extracted** requirements (the real system) and with **gold**
   requirements (isolates rule errors from extraction errors).

## Results

| Set | Requirements | Accuracy | Macro-F1 | **False acceptance** | False blocking |
|---|---|---|---|---|---|
| Dev (29) | extracted | 1.000 | 1.000 | 0.000 | 0.000 |
| Dev (29) | gold | 1.000 | 1.000 | 0.000 | 0.000 |
| **Held-out (24), blind** | extracted | **0.625** | 0.641 | **0.000** | **0.429** |
| **Held-out (24), blind** | gold | **0.750** | 0.848 | **0.000** | **0.429** |

On the dev set, the pipeline went from 0.241 (Phase 2) to 0.310, 0.414 and now 1.000. The only
number that estimates real performance is the **held-out** row.

**Reading it:** the rules are **safe but too strict**. No invalid resolution was accepted (false
acceptance 0 on both runs; a benchmark test now requires this to stay 0). But 6 of 14 valid
resolutions were rejected, because they used patterns the rules do not model.

### Held-out error analysis

| Case | Expected → got | Cause | Kind |
|---|---|---|---|
| `h-validation-helper-call` | S → N | validation delegated to `validate_email(email)`; rules do not follow calls | limitation: no interprocedural analysis |
| `h-validation-moved-to-helper` | S → N | check lives in a new helper that `save()` calls; the helper is new code, so line mapping cannot link it | limitation: interprocedural |
| `h-errors-avoided-with-get` | S → N | `KeyError` avoided with `dict.get()` instead of caught | limitation: alternative idioms |
| `h-log-in-branch` | S → N / U | log check only looks inside `except` handlers, not `if` branches | rule gap |
| `h-testing-parametrize-none` | S → N | `None` is supplied via `@pytest.mark.parametrize`, outside the test body | rule gap |
| `h-testing-already-covered` | S → N | "empty" only recognises `""`, not `[]` | rule gap |
| `h-api-abort-404` | S → U (extracted only) | "Respond with…" is not a known request verb | extraction gap |
| `h-validation-early-return` | S → N (extracted only) | "Return early … instead of crashing" categorised as error handling | extraction gap |
| `h-api-404-without-log` | P → N (extracted only) | "log the lookup failure" is checked against handlers only | rule gap (shared with `h-log-in-branch`) |

## Phase 5.1: hardening (after the blind run, disclosed)

Fixes for the gaps found above. Each fix has a positive test **and an adversarial counterpart** on
new snippets (`tests/rules/test_hardening.py`); nothing was tuned on the held-out cases themselves.

| # | Fix | Guarded against (adversarial test) |
|---|---|---|
| 1 | Logging on a failure path counts in `if` branches too, not only in `except` handlers | a log outside any failure path |
| 2 | Test inputs include decorators (`@pytest.mark.parametrize`) | — |
| 3 | Empty collections (`[]`, `{}`, `()`) count as "empty" | a non-empty collection |
| 4 | **Same-file helpers are followed one level** (argument → parameter → rejecting guard of the requested kind). An **imported** helper named like a validator is **inconclusive → human review**, never accepted | helper that doesn't check; checks the wrong kind; is called after the operation; an unrelated imported call |
| 5 | `.get()` newly avoiding a `KeyError` counts as handling it | a pre-existing `.get()` elsewhere |
| 6 | API: request words ("the **invoice**") reach derived variables (`row = load_invoice(invoice_id)`) | a status on an unrelated branch (`if debug_mode:`) |
| 7 | Extraction: `respond` / `reply` / `abort` are request verbs; "return early" is a validation cue | — |

**A pre-existing false-acceptance risk was found by fix 6's adversarial test.** When the
request's condition matched no identifier, the API rule accepted the status on *any* conditional
branch. Now such cases are **inconclusive** (human review).

### Results after hardening

| Set | Requirements | Accuracy | False acceptance | False blocking |
|---|---|---|---|---|
| Dev (29) | extracted / gold | 1.000 / 1.000 | 0.000 / 0.000 | 0.000 / 0.000 |
| Held-out (24), **not blind any more** | extracted | 0.625 → **0.875** | 0.000 → **0.000** | 0.429 → **0.071** |
| Held-out (24), **not blind any more** | gold | 0.750 → **0.875** | 0.000 → **0.000** | 0.429 → **0.143** |

Remaining held-out misses:
- `h-validation-helper-call` → UNCERTAIN, as intended (imported validator, not analysable).
- `h-log-in-branch` (extracted only): "Log a warning when …" is not recognised as error handling.
- `h-testing-already-covered`: `ReviewCase` carries only *changed* test files, so an untouched
  covering test is invisible (data limitation).
- `h-errors-avoided-with-get` (gold only): the gold wording names no exception.

**The held-out set is no longer a blind measure.** The next blind measurement is the Phase 9
benchmark. Reports: `experiments/phase5_1_heldout_after_hardening*.json`.

## Roadmap targets

| Target | Status |
|---|---|
| Unit tests for every rule: positive, negative, adversarial | ✅ `tests/rules/` (46 tests, plus aggregator decision table) |
| ≥ 4 categories working end-to-end | ✅ on dev (all 5). Held-out: naming 100%, API 100% (gold), validation 71%, errors 60%, testing 33% |
| Lexical false positives → NOT_SATISFIED | ✅ dev 4/4, held-out 1/1 |
| Rules module coverage ≥ 90% | ✅ 93–100% per module |

## Limitations (known, not hidden)

- **No interprocedural analysis:** checks done by a called helper are not seen.
- **Idiom coverage:** alternative ways of meeting a request (`dict.get`, context managers,
  decorators) are rejected rather than recognised. This is safe (no false acceptance) but it blocks
  valid work.
- **Syntactic, not semantic:** "the guard precedes the operation" is line order within the
  target, not control-flow dominance.
- **Evaluation data is author-written.** Independent, annotated real-world cases come in Phase 9.

## Commands

```bash
uv run verireview verify-fixture dataset/fixtures/api-003-wrong-status-code
uv run verireview eval-fixtures                                   # dev, extracted requirements
uv run verireview eval-fixtures --gold-requirements               # dev, gold requirements
uv run verireview eval-fixtures --root dataset/heldout_fixtures   # held-out
```
