# Phase 2: Local Verifier and Dev Fixtures

**Goal:** `comment + before + after → preliminary verdict`, with no GitHub access. It also
establishes the contracts, pipeline and evaluation harness that every later phase plugs into.

## Pipeline

```text
ReviewCase (from GitHub ingestion OR a fixture: same model)
   │
   ├─ requirement stage   requirements/stub.py      whole comment = 1 requirement   (Phase 4 replaces)
   ├─ evidence stages     evidence/locality.py      file changed? near comment? tests changed?
   │                                                (Phase 3 AST, Phase 5 rules, Phases 6-7 semantic: added here)
   ├─ aggregator          verification/preliminary.py   explicit decision table   (Phase 8 replaces)
   └─ explanation         explanations/text.py      built only from recorded evidence
   → VerificationResult (verdict, confidence, per-requirement status, evidence, explanation, pipeline_version)
```

Contract guarantees (enforced by validators, tested):
- Every `Evidence` has a code location **or** an explicit `no_location_reason`.
- Every evidence id a requirement cites exists in the result, and ids are unique.
- The explanation contains every evidence item verbatim and nothing else factual.
- Confidence is `HIGH`/`MEDIUM`/`LOW` only. No numeric percentages before calibration (plan §15).

## Dev fixtures (`dataset/fixtures/`)

29 hand-written cases. Each has a `meta.json` with the expected verdict, a written **rationale**
and the **gold requirements**, which Phase 4 extraction will be scored against.

| | SATISFIED | PARTIAL | NOT | UNCERTAIN | total |
|---|---|---|---|---|---|
| naming | 2 | 1 | 2 | 1 | 6 |
| validation | 2 | 1 | 4 | 0 | 7 |
| testing | 1 | 1 | 3 | 0 | 5 |
| error handling | 2 | 1 | 2 | 1 | 6 |
| API behaviour | 1 | 1 | 2 | 1 | 5 |
| **total** | **8** | **5** | **13** | **3** | **29** |

Hard cases: lexical false positive ×4, partial ×5, unrelated change ×4, pre-existing ×1
(ADR-001), wrong target ×2, wrong order ×1, wrong value ×1, ambiguous ×3.
`tests/benchmark/test_fixture_dataset.py` enforces these minimums, so the set cannot quietly shrink.

This is the **dev set**: it may be used for tuning. The frozen **test set** comes in Phase 9.

## Baseline result (`experiments/phase2_locality_baseline.json`)

Pipeline `phase2-locality-1`, dataset hash `1754164a4b78…`:

| Metric | Value |
|---|---|
| Accuracy | **0.241** |
| Macro-F1 | 0.097 |
| False acceptance rate | **1.000**: every invalid resolution was accepted |
| False blocking rate | 0.125 |
| Correct, by hard case | 0.00 on every hard-case type; 0.88 on ordinary cases |

This is the result the plan predicts for "something changed near the comment ⇒ satisfied". It
accepts every lexical trap (a comment mentioning `discount_rate`, a TODO mentioning `201 Created`),
every unrelated edit and every partial fix. It is the **floor**: later phases must beat it
measurably on the same dataset hash.

## Commands

```bash
uv run verireview verify-fixture dataset/fixtures/validation-007-logging-change
uv run verireview verify-case case.json            # a ReviewCase from `verireview ingest`
uv run verireview eval-fixtures --out experiments/<name>.json
```

## Open decision

**ADR-001 (pre-existing implementation)** is *Proposed*. See `docs/adr/001-pre-existing-implementation.md`.
