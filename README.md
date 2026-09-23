# VeriReview

**Evidence-based verification of GitHub pull-request review resolution.**

A developer can mark a review thread as *resolved* without actually meeting the reviewer's
requirement. VeriReview answers one question:

> **Did the code changes made after the review comment actually satisfy the review requirement?**

It reconstructs the review thread from GitHub, extracts what the reviewer asked for, finds the
relevant code, and checks it structurally. The result is a verdict backed by cited evidence:

`SATISFIED` · `PARTIALLY_SATISFIED` · `NOT_SATISFIED` · `UNCERTAIN`

A separate policy layer turns the verdict into `ALLOW` / `WARN` / `HUMAN_REVIEW` / `BLOCK`.
**Blocking is disabled** (plan §4: not before the system is evaluated and calibrated).

---

## Status

| | |
|---|---|
| **Current phase** | **Phase 6 done: NLP baselines.** The MVP (Phase 8a, all 15 plan §28 criteria) is complete |
| **Next phase** | Phase 7: one code-aware model (e.g. CodeBERT) as an evidence source |
| **Verdict accuracy (rules)** | dev set 1.000 (training data) · held-out **0.875** with **zero false acceptances** (not blind after Phase 5.1) |
| **NLP baselines** | keyword / TF-IDF / embeddings: dev ROC-AUC < 0.5 (fooled by lexical traps); held-out AUC 0.56–0.69, but 25–88% false acceptance at any usable threshold |
| **Requirement extraction** | blind held-out: count exact 0.844, category F1 0.909 |
| **Tests** | 635 unit + 8 integration + 1 model test, strict mypy, 96% coverage, CI on every push |

---

## How it works

```text
GitHub PR ──► ingestion ──► ReviewCase ──► requirement extraction ──► evidence ──► aggregation ──► policy
  (REST +      thread +       (before/after     comment → categorised     diff, AST,     verdict +      ALLOW / WARN /
   GraphQL)    commit window   code, diff,      requirements +            rules,         confidence +   HUMAN_REVIEW
               + flags         tests)           ambiguity score           tests          explanation    (no BLOCK)
```

| Stage | What it does | Phase |
|---|---|---|
| Ingestion | Rebuilds the review thread and the **temporal window** of commits made after the comment (handles rebases/force-pushes, flags unreliable cases) | 1 |
| Location | Finds the commented function after the changes, even if renamed, moved or extracted into a helper (Tree-sitter) | 3 |
| Requirements | Splits the comment into atomic requirements (naming, validation, testing, error handling, API behaviour), with targets, conditions and an **ambiguity score** | 4 |
| Rules | One deterministic rule per category, querying code *structure*: guards, handlers, responses, test inputs. A comment that only *mentions* the fix never counts | 5 |
| Aggregation | Per-requirement status → overall verdict. Ambiguous requests → `UNCERTAIN`. Confidence is lowered when the case is unreliable | 5, 8a |
| Policy | Verdict × confidence → action, in observe / advisory / human-review / enforcement mode | 8a |
| NLP baselines | Keyword overlap, TF-IDF and sentence-embedding similarity between comment and added code, scored by the same harness, for comparison ([results](#nlp-baselines)) | 6 |

Semantic models (Phase 7) will be **one evidence source, never the final authority**. Phase 6
showed why: text similarity rewards a comment that merely *repeats* the reviewer's words.

## Example

"Validate username and return HTTP 400" (plan §16), when the developer added validation but no
400 response. Real output of `verireview verify-fixture dataset/fixtures/api-002-validation-without-400`,
abridged to 6 of its 19 evidence lines:

```text
Review request:
"Please validate `username` (non-empty, max 32 chars) and return HTTP 400 on invalid input."

Requirements:
✓ R1 (validation): validate `username` (non-empty, max 32 chars)
✗ R2 (api_behavior): return HTTP 400 on invalid input

Evidence:
• [E3] Commented line 10 is in function `signup`. (web/signup.py:7-11 @ 64d302f (before))
✓ [E15] Emptiness check `not username or len(username) > 32` on `username` raises `ValueError` (line 11). (web/signup.py:11-12 @ 6ba2693 (after))
✓ [E16] Range check `not username or len(username) > 32` on `username` raises `ValueError` (line 11). (web/signup.py:11-12 @ 6ba2693 (after))
✓ [E17] R1 (validation) satisfied: `username` is checked before use. (web/signup.py:11-12 @ 6ba2693 (after))
✗ [E18] No response with HTTP 400 on the requested branch.
✗ [E19] R2 (api_behavior) not_satisfied: HTTP 400 is not returned where requested.

Result:
PARTIALLY_SATISFIED

Confidence:
MEDIUM

Recommended action:
HUMAN_REVIEW (advisory mode). Only part of the request appears satisfied.
```

---

## Quickstart

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), Docker.

```bash
cp .env.example .env
uv sync
uv run pytest                     # unit tests
docker compose up -d --build      # API on http://localhost:8000, PostgreSQL on host port 5433
uv run pytest -m integration      # integration tests (need the database)
```

Optional NLP models (sentence-transformers + PyTorch CPU, ~300 MB; not needed by the service):

```bash
uv sync --group nlp
uv run --group nlp verireview eval-baselines   # downloads all-MiniLM-L6-v2 (~90 MB) once
```

## Usage

### Command line

| Command | Purpose |
|---|---|
| `verireview threads OWNER/REPO PR` | List a PR's review threads and their comment ids |
| `verireview ingest OWNER/REPO PR --comment-id ID [--out f.json] [--no-db]` | Build a `ReviewCase` from GitHub |
| `verireview verify-case f.json [--json]` | Verify an ingested case (verdict, explanation, policy) |
| `verireview verify-fixture DIR` | Verify one hand-written fixture |
| `verireview extract "comment text" [--code f.py --line N]` | Show the structured requirements extracted from a comment |
| `verireview eval-fixtures [--root DIR] [--pipeline NAME] [--gold-requirements]` | Evaluate verdicts: accuracy, F1, confusion matrix, false acceptance and blocking |
| `verireview eval-requirements` | Evaluate requirement extraction on the dev and held-out sets |
| `verireview eval-baselines [--scorers lexical,tfidf,embedding]` | Compare NLP baselines with the rules on dev and held-out (embedding needs the `nlp` group) |

Run with `uv run verireview …` (or `python -m uv run verireview …`). Set
`VERIREVIEW_GITHUB_TOKEN` (fine-grained, read-only) for thread resolution state and higher rate
limits.

### HTTP API

| Endpoint | Body | Returns |
|---|---|---|
| `POST /verify` | `{"case": ReviewCase, "pipeline"?: name}` | `{"result": VerificationResult, "policy": PolicyDecision}` |
| `POST /verify/github` | `{"repository": "owner/repo", "pull_number": N, "comment_id": N}` | same |
| `GET /health`, `GET /health/db` | — | liveness / database readiness |

```bash
curl -X POST localhost:8000/verify/github -H "content-type: application/json" \
     -d '{"repository": "owner/repo", "pull_number": 1, "comment_id": 123}'
```

---

## Evaluation results

All pipelines are evaluated on the same pinned datasets (hashes recorded in `experiments/`).

**Verdicts, dev fixtures (29):** used while building the rules, so these are *training* numbers.

| Pipeline | Accuracy | Macro-F1 | False acceptance ↓ | False blocking ↓ |
|---|---|---|---|---|
| `phase2-locality`: "changed near the comment" baseline | 0.241 | 0.097 | 1.000 | 0.125 |
| `phase3-structure`: changed code in the commented function | 0.310 | 0.165 | 0.889 | 0.125 |
| `phase4-requirements`: + requirement extraction, ambiguity gate | 0.414 | 0.425 | 0.889 | 0.125 |
| `phase5-rules` / `mvp`: + per-category rules | 1.000 | 1.000 | 0.000 | 0.000 |

**Verdicts, held-out fixtures (24):** written after the rules were frozen.

| Run | Accuracy | False acceptance | False blocking |
|---|---|---|---|
| Phase 5, **blind** | 0.625 | **0.000** | 0.429 |
| After Phase 5.1 hardening (**not blind**; fixes disclosed in [docs/phase5_rules.md](docs/phase5_rules.md)) | 0.875 | **0.000** | 0.071 |

**Requirement extraction:**

| Set | Count exact (target ≥ 0.80) | Category F1 (target ≥ 0.85) |
|---|---|---|
| Dev (29 comments) | 0.966 | 0.987 |
| Held-out (32 comments), **blind** | **0.844** | **0.909** |

### NLP baselines

Similarity between the comment and the added code, with the threshold tuned on dev and frozen for
held-out ([details](docs/phase6_nlp_baselines.md)). Operating point: Youden's J. The
accuracy-tuned threshold collapses every baseline to "always NOT_SATISFIED".

| Verifier | Held-out accuracy | False acceptance | False blocking | ROC-AUC dev / held-out |
|---|---|---|---|---|
| Lexical overlap | 0.542 | 0.875 | 0.071 | 0.406 / 0.674 |
| TF-IDF | 0.500 | 0.250 | 0.500 | 0.396 / 0.558 |
| Embeddings (MiniLM) | 0.542 | 0.750 | 0.214 | 0.465 / 0.688 |
| **Rules (`mvp`)** | **0.875** | **0.000** | 0.071 | — |

An AUC below 0.5 on dev means invalid fixes scored *higher* than valid ones: comments and TODOs
that repeat the request look similar to it. Small samples (about 20 valid-vs-invalid cases per set);
confidence intervals come in Phase 10.

False acceptance (a bad fix accepted) is the safety-critical metric. A benchmark test requires it
to stay 0 for the rules on the held-out set.

---

## Phase progress

| Phase | | What | Doc |
|---|---|---|---|
| 0 | ✅ | Project setup: uv, FastAPI, PostgreSQL + Alembic, Docker, CI | [ROADMAP](docs/ROADMAP.md) |
| 1 | ✅ | GitHub ingestion, temporal window, live check on 8 real PRs | [phase1](docs/phase1_github_ingestion.md), [live checks](docs/phase1_live_checks.md) |
| 2 | ✅ | Contracts, 29 dev fixtures, evaluation harness, baseline | [phase2](docs/phase2_local_verifier.md) |
| 3 | ✅ | Diff + Tree-sitter: symbols, facts, location resolution | [phase3](docs/phase3_diff_ast.md) |
| 4 | ✅ | Requirement extraction + ambiguity, blind held-out set | [phase4](docs/phase4_requirements.md) |
| 5 / 5.1 | ✅ | Per-category rules, blind held-out verdicts, hardening | [phase5](docs/phase5_rules.md) |
| 8a | ✅ | **MVP:** confidence, policy, explanations, API, end-to-end tests | [phase8a](docs/phase8a_mvp.md) |
| 6 | ✅ | NLP baselines: keyword, TF-IDF, embeddings, common harness | [phase6](docs/phase6_nlp_baselines.md) |
| 7 | ⏳ | One code-aware model (e.g. CodeBERT) as an evidence source | — |
| 9 | | Benchmark: real-world cases, two annotators, agreement | — |
| 10 | | Evaluation: ablation study, calibration | — |
| 11–13 | | GitHub advisory mode, staged enforcement, dashboard | — |

Decisions: [ADR-001](docs/adr/001-pre-existing-implementation.md), where code that already did
what was asked counts as SATISFIED (confidence at most MEDIUM).

## Project layout

```text
src/verireview/
  gh/            GitHub REST + GraphQL client (auth, retries, rate limits)
  threads/       review-thread reconstruction
  ingestion/     temporal window, ReviewCase assembly, storage
  contracts/     ReviewCase, ReviewRequirement, Evidence, VerificationResult (Pydantic)
  diff/          unidiff / difflib
  syntax/        Tree-sitter: symbols, facts, structural diff, location resolution
  requirements/  rule-based requirement extraction (lexicon in one file)
  evidence/      evidence stages: structure, tests, requirements, rules
  rules/         one rule per category + structural queries
  verification/  pipelines, aggregators, ambiguity gate, reliability
  explanations/  evidence-citing explanations
  policy/        ALLOW / WARN / HUMAN_REVIEW / BLOCK
  semantic/      NLP baselines: text views, lexical / TF-IDF / embedding scorers, similarity verifier
  evaluation/    metrics, common Verifier harness, extraction and baseline evaluation
  api/  db/  cli.py  config.py
dataset/         fixtures (dev), heldout_fixtures (verdicts), requirements (held-out comments)
experiments/     evaluation reports (JSON)
docs/            roadmap, per-phase docs, ADRs
```

## Configuration

Environment variables (prefix `VERIREVIEW_`, see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://…@localhost:5433/verireview` | PostgreSQL |
| `GITHUB_TOKEN` | — | Optional. Read-only PAT: resolution state, 5,000 req/h |
| `POLICY_MODE` | `advisory` | `observe` / `advisory` / `human_review` / `enforcement` |
| `POLICY_ALLOW_BLOCK` | `false` | Only valid with `enforcement`. Must stay off until Phase 12 |

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest && uv run pytest -m integration
uv run --group nlp pytest -m model            # needs the downloaded model
uv run verireview eval-fixtures && uv run verireview eval-requirements
uv run --group nlp verireview eval-baselines
```

Dependency groups: runtime (the service), `dev` (tests, lint, scikit-learn), and optional `nlp`
(sentence-transformers, PyTorch CPU). The Docker image contains only the runtime.

Working rules (see [CLAUDE.md](CLAUDE.md)): one phase at a time; every rule has positive,
negative and adversarial tests; evaluation sets are hash-pinned and never tuned against; repository
content is treated as untrusted data.

## Safety and limitations

- **Never blocks merges** by default. Blocking requires enforcement mode *and* an explicit opt-in,
  and a test pins that default.
- **Confidence is rule-based, not calibrated.** HIGH is never emitted before Phase 10.
- **Evaluation data is author-written.** The held-out verdict set is no longer blind. An
  independently annotated benchmark comes in Phase 9.
- **Rules are structural, not semantic:** no control-flow analysis. Helpers are followed one level
  deep, and only within the same file.
- **Python only**, one commented file per case.
- **NLP baselines are not used for verdicts.** They are measured for comparison only; at every
  usable threshold they accept invalid fixes.

## Documentation

- Design: [VERIREVIEW_PLAN.md](VERIREVIEW_PLAN.md) · Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Per phase: [1](docs/phase1_github_ingestion.md) · [1 live](docs/phase1_live_checks.md) ·
  [2](docs/phase2_local_verifier.md) · [3](docs/phase3_diff_ast.md) ·
  [4](docs/phase4_requirements.md) · [5](docs/phase5_rules.md) · [8a](docs/phase8a_mvp.md) ·
  [6](docs/phase6_nlp_baselines.md)
- Decisions: [docs/adr/](docs/adr/)
