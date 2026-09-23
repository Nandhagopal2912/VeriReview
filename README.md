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

> Status: **Phase 0**. Project skeleton only; no verification logic yet.

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
