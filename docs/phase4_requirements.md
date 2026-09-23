# Phase 4: Requirement Representation

**Goal (roadmap):** turn a review comment into a structured `ReviewRequirement` with 1..N atomic,
categorised requirements, plus an ambiguity score that routes unclear requests to a human.

## Schema (`contracts/requirement.py`, schema v2)

`ReviewRequirement`: `target_file`, `target_symbol` (enclosing function of the commented line),
`requirements[]`, `actionable` (False for e.g. "LGTM"), `ambiguity` ∈ [0, 1] + `ambiguity_reasons`,
`utterances[]` (each sentence's type), `source` (`manual` | `extracted` | `stub`).

`Requirement`: `id`, `category` (naming · validation · testing · error_handling · api_behavior ·
other), `description`, `target`, `condition`, `expected_behavior`, `suggested_code` (from GitHub
```` ```suggestion ```` blocks).

## Extraction pipeline (`requirements/`, rule-based, deterministic)

```text
comment
 → prepare: extract ```suggestion blocks; drop code blocks, quotes, HTML, URLs, bullets
 → mask inline `code`, parentheticals, "e.g." so no split happens inside them
 → sentences → utterance type: requirement · suggestion (hedged) · question · explanation · chit-chat
 → actionable sentences → clauses (split only where the next part starts with a request verb)
     "Catch X, retry once, and raise Y if it fails"  → 3 clauses
     "between 0 and 150", ", we have no trace…"       → no split
     leading "If/when …" clause → condition of the next request
 → expansion of coordinated objects: two renames, "tests for A and B", "handle E1 and E2",
   "validate `a` and `b`", "`x` is P1 and P2"
 → category per requirement from lexical cues (testing, naming decisive; API > error > validation
   on ties; raising ValueError/TypeError = validation); cue-less clauses inherit their neighbour's
 → target: backticked identifier (preferring ones in the code) → plain word/bigram in the code
 → ambiguity score
```

All word lists and weights are in `requirements/lexicon.py`.

### Ambiguity (not a probability: an additive score over explicit signals)

| Signal | Weight |
|---|---|
| Genuine question (not "could you …?") | 0.50 |
| Hedged ("maybe", "probably", "consider", "hmm", …) | 0.35 |
| No identifiable code target | 0.20 |
| Asks for a hard-to-verify property (idempotent, cache, refactor, split, …) | 0.20 |
| Vague wording ("better", "something", "cleaner", …) | 0.15 |
| No actionable request at all | 1.00 |

A request with a score of 0.5 or more is **UNCERTAIN**: the ambiguity gate (`verification/ambiguity.py`)
sends it to a human whatever the code did.

## Evaluation protocol: dev set + blind held-out set

- **Dev set:** gold requirements of the 29 dev fixtures (written in Phase 2).
- **Held-out set:** `dataset/requirements/heldout.jsonl`, 32 comments deliberately phrased
  differently (polite questions, `nit:`, arrows, suggestion blocks, "LGTM", …). It was **written and
  hashed before any extractor code existed** (sha256 `13fe7399…`). A benchmark test pins the hash,
  so any edit fails CI.
- Limitation: both sets were written by the same author as the extractor. Independent
  annotation comes in Phase 9.

## Results

| Metric (target) | Dev | Held-out, **blind first run** | Held-out after fixes (not blind) |
|---|---|---|---|
| Requirement count exact (≥ 0.80) | 0.966 | **0.844** | 0.938 |
| Category F1 (≥ 0.85) | 0.987 | **0.909** | 0.974 |
| Actionable accuracy | 1.000 | 0.938 | 1.000 |
| Ambiguity precision / recall | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| Target function found | 1.000 | n/a | n/a |

Both targets are met on the blind run. The fixes made after it (all disclosed):

| Fix | Kind | Seen in |
|---|---|---|
| In-clause condition was counted twice when categorising | bug | dev `api-003`, held-out `h18` |
| "should **probably cache**": modal check only looked at the first word | bug | held-out `h12` |
| Validation subject expansion did not require coordination ("A **and** B") | bug | held-out `h23` |
| Genuine-question weight 0.4 → 0.5 | tuning | dev `errors-005` |
| "Consider rena**ming**" (hedged gerund request) | coverage gap | held-out `h32` |

Remaining misses are granularity disagreements with the gold, left as they are:
"log it and raise X" as 1 or 2 requirements (`errors-001`), "a docstring and type hints" (`h01`),
"don't swallow; re-raise" (`h17`).

Reports: `experiments/phase4_requirements_blind_run.json` (blind),
`experiments/phase4_requirements.json` (after fixes).

## Effect on verification (dev fixtures, dataset `1754164a4b78…`)

| Pipeline | Accuracy | Macro-F1 | False acceptance | UNCERTAIN recall |
|---|---|---|---|---|
| `phase2-locality-1` | 0.241 | 0.097 | 1.000 | 0 / 3 |
| `phase3-structure-1` | 0.310 | 0.165 | 0.889 | 0 / 3 |
| `phase4-requirements-1` | **0.414** | **0.425** | 0.889 | **3 / 3** (no false alarms) |

The remaining errors are "the code changed, but not in the requested way" (partial fixes, wrong
target, wrong order, wrong status code). The Phase 5 rules close that gap using the categorised
requirements from this phase and the structural facts from Phase 3.

## Commands

```bash
uv run verireview extract "Please validate username, return HTTP 400 on invalid input, and add a test."
uv run verireview eval-requirements --out experiments/phase4_requirements.json
uv run verireview eval-fixtures                       # default pipeline: phase4-requirements
```
