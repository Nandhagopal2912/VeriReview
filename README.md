# VeriReview

**Evidence-based verification of GitHub pull-request review resolution.**

A developer can mark a review thread as resolved without actually meeting the reviewer's
requirement. VeriReview answers one question: *did the code changes made after the comment
actually satisfy the review requirement?* It combines diff, AST, rule, test and semantic
evidence to reach a verdict:

`SATISFIED` · `PARTIALLY_SATISFIED` · `NOT_SATISFIED` · `UNCERTAIN`

Every verdict comes with the evidence behind it. VeriReview does not block merges automatically.

- Design: [VERIREVIEW_PLAN.md](VERIREVIEW_PLAN.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

> Status: **Phase 5**. GitHub ingestion, Tree-sitter structural analysis, requirement
> extraction and deterministic per-category verification rules. Blind held-out result: accuracy
> 0.625 with **zero false acceptances**. After the disclosed Phase 5.1 hardening: 0.875, still
> zero false acceptances, with false blocking down from 43% to 7%.
> See [docs/phase5_rules.md](docs/phase5_rules.md).

```bash
uv run verireview extract "Please validate username, return HTTP 400 on invalid input, and add a test."
```

## Verify and evaluate

```bash
uv run verireview verify-fixture dataset/fixtures/validation-001-none-check
uv run verireview eval-fixtures
```

## Ingest a review thread

```bash
uv run verireview threads OWNER/REPO PR_NUMBER
uv run verireview ingest OWNER/REPO PR_NUMBER --comment-id COMMENT_ID --out case.json --no-db
```

Set `VERIREVIEW_GITHUB_TOKEN` in `.env` to get thread resolution state (see
[docs/phase1_github_ingestion.md](docs/phase1_github_ingestion.md)).

## Quickstart

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), Docker.

```bash
cp .env.example .env
uv sync
uv run pytest
```

Run the full stack (API on http://localhost:8000, PostgreSQL on host port 5433):

```bash
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8000/health/db
```

Run integration tests against the database:

```bash
docker compose up -d db
uv run pytest -m integration
```
