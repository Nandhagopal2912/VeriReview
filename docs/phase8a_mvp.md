# Phase 8a: MVP (evidence aggregation, confidence, policy, API)

## What Phase 8a adds on top of Phases 1–5.1

| Component | Module | What it does |
|---|---|---|
| Reliability-based confidence | `verification/reliability.py` | Lowers confidence to **LOW** (never raises it) when the case itself is shaky: history rewritten, timestamp ordering, reviewed file or commented line unavailable, truncated commit list, whole-PR file list, parser errors, or borderline ambiguity. Each reason is written into the notes. HIGH stays withheld until Phase 10 calibration |
| Policy layer | `policy/decision.py` | (verdict, confidence) → ALLOW / WARN / HUMAN_REVIEW / BLOCK (plan §4), then the operating mode (plan §27: observe / advisory / human_review / enforcement). **BLOCK needs enforcement mode *and* `allow_block`; both are off by default**, and a test pins that |
| Explanations | `explanations/text.py` | Plan §16 format: request, per-requirement ✓ satisfied / ✗ missing / ~ partial / ? undecided, every evidence line with `file:line @ commit`, result, confidence, notes |
| API | `api/verify.py` | `POST /verify` (ReviewCase → result + policy) and `POST /verify/github` (owner/repo + PR + comment id → ingest → verify). GitHub errors map to 404 / 503 / 502 |
| MVP pipeline | `verification/__init__.py` | `mvp-1` = extraction → requirement, structural, test and rule evidence → ambiguity gate → reliability → rule aggregator. It is the default; phases 2–5 stay runnable |

Policy mapping:

| Verdict | Confidence | Recommended | Default action (advisory) |
|---|---|---|---|
| SATISFIED | MEDIUM | ALLOW | ALLOW |
| SATISFIED | LOW | HUMAN_REVIEW | HUMAN_REVIEW |
| PARTIALLY_SATISFIED | any | HUMAN_REVIEW | HUMAN_REVIEW |
| UNCERTAIN | any | HUMAN_REVIEW | HUMAN_REVIEW |
| NOT_SATISFIED | MEDIUM | BLOCK | **WARN** (blocking disabled) |
| NOT_SATISFIED | LOW | HUMAN_REVIEW | HUMAN_REVIEW |

Settings: `VERIREVIEW_POLICY_MODE` (default `advisory`), `VERIREVIEW_POLICY_ALLOW_BLOCK`
(default `false`; only valid together with `enforcement`).

## Example (containerised API, `POST /verify`, fixture `api-002`)

```text
Review request:
"Please validate `username` (non-empty, max 32 chars) and return HTTP 400 on invalid input."

Requirements:
✓ R1 (validation): validate `username` (non-empty, max 32 chars)
✗ R2 (api_behavior): return HTTP 400 on invalid input
…
Result: PARTIALLY_SATISFIED   Confidence: MEDIUM   Policy: HUMAN_REVIEW (blocks_merge: false)
```

This is the plan §16 example, produced end to end.

## MVP Definition of Done (plan §28)

| # | Criterion | Status | Proof |
|---|---|---|---|
| 1 | GitHub PR can be retrieved | ✅ | `gh/api.py`; `tests/unit/gh/`; live check on 8 real PRs (`docs/phase1_live_checks.md`) |
| 2 | Review thread can be reconstructed | ✅ | `threads/reconstruct.py`; `tests/unit/threads/` |
| 3 | Comment context is available | ✅ | `ReviewThread.comments`, `diff_hunk`, `anchor_line`; `tests/unit/ingestion/test_assemble.py` |
| 4 | Original and subsequent commits are identified | ✅ | `ingestion/window.py` (incl. rewritten history); `tests/unit/ingestion/test_window.py` |
| 5 | Relevant diff can be extracted | ✅ | `ReviewCase.unified_diff`, `diff/unified.py`; `tests/unit/diff/` |
| 6 | Relevant function/symbol can be identified | ✅ | `syntax/location.py`; 29/29 dev fixtures + 9 move scenarios (`tests/unit/syntax/test_location.py`) |
| 7 | Tree-sitter parses the target code | ✅ | `syntax/parser.py` (pinned); robustness tests on invalid code |
| 8 | At least 4 deterministic review categories work | ✅ | 5 rules (`rules/`); dev 29/29; held-out 0.875, false acceptance 0 (`docs/phase5_rules.md`) |
| 9 | Structured requirement representation exists | ✅ | `contracts/requirement.py` + extraction; blind held-out F1 0.909 (`docs/phase4_requirements.md`) |
| 10 | Evidence is collected | ✅ | 5 evidence stages; every item located or explained (validator + tests) |
| 11 | Verifier returns a verdict | ✅ | `mvp-1`; `POST /verify`; `verify-fixture` / `verify-case` |
| 12 | Explanation cites actual evidence | ✅ | every evidence item appears verbatim with `file:line @ commit` (`tests/unit/explanations/`, pipeline tests over all fixtures) |
| 13 | Unit tests exist for every rule | ✅ | `tests/rules/` (positive, negative, adversarial per rule; rules coverage 93–100%) |
| 14 | Integration tests exist for the pipeline | ✅ | `tests/integration/test_end_to_end.py`: GitHub (recorded) → ReviewCase → PostgreSQL → reload (unchanged) → verify → policy |
| 15 | No automatic merge blocking is enabled | ✅ | `policy/decision.py` defaults; `test_default_configuration_never_blocks` |

## Honest status of the MVP

- **Measured quality:** dev set 1.000 (training data). Held-out 0.875 with **zero false acceptances**,
  but that set is **no longer blind** after Phase 5.1. The next blind, independently annotated
  measurement is Phase 9.
- **Confidence levels are not calibrated.** They are rule-based, and HIGH is not emitted before Phase 10.
- **Not included yet:** GitHub App auth, webhooks, posting results, audit trail (Phase 11); NLP
  baselines and a code-aware model (Phases 6–7); a benchmark with inter-annotator agreement (Phase 9).

## Commands

```bash
uv run verireview verify-fixture dataset/fixtures/api-002-validation-without-400
uv run verireview verify-case case.json --json          # {"result": …, "policy": …}
docker compose up -d --build
curl -X POST localhost:8000/verify -H "content-type: application/json" -d '{"case": …}'
curl -X POST localhost:8000/verify/github -H "content-type: application/json" \
     -d '{"repository": "owner/repo", "pull_number": 1, "comment_id": 123}'
```
