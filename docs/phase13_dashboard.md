# Phase 13: Read-only Dashboard

A dashboard for the operator of the GitHub App. For each repository, pull request and resolved
review thread it shows what VeriReview concluded and why:

- the thread;
- each requirement with its category and status;
- every piece of evidence with its file, lines and commit;
- the explanation;
- the commented code before and after, and the diff;
- verdict, confidence and suggested action;
- the history of earlier verifications, rollout stages and reviewer confirmations.

The dashboard only reads. Nothing on it changes a verdict, a stage or GitHub.

Owner decisions (2026-09-24):

- **Stack:** server-rendered pages in the existing FastAPI service, with Jinja2 templates and **no
  JavaScript at all**. This departs from the roadmap's Next.js line: one container, no Node
  toolchain, a smaller attack surface, tested with pytest. Jinja2 became a runtime dependency; it
  was already in `uv.lock`.
- **Access:** one **operator token**, and the dashboard is **off by default**.
- **Code storage:** the worker stores the exact verified ReviewCase with each audit row, and
  `purge-audit` removes it after a **retention** period (default 90 days).

## Pages

| URL | Shows |
|---|---|
| `/dashboard` | Verdict and job totals; the enforcement gate (global switch, eligible categories: none) and retention; repositories with their stage, pull requests, verifications and last activity |
| `/dashboard/r/{installation}/{owner}/{repo}` | Rollout stage, reviewer confirmations, pull requests (thread count, latest verdicts, head), stage history (who, when, from, to, why) |
| `…/pull/{n}` | Each resolved thread: latest verdict, confidence, action, head, and links to earlier verifications |
| `/dashboard/audit/{id}` | One verification: header (verdict · confidence · action, head, pipeline version, **inputs sha256**), the thread, requirements (category, status, evidence ids), explanation, the evidence table (✓/✗/•, fact, kind, file:lines@commit), the code before (commented line highlighted) and after (lines cited by evidence highlighted), and the diff |
| `/dashboard/jobs` | The latest 100 queue jobs: event, kind, status, attempts, last error |

It was checked visually in the browser pane: pages rendered by the real routes, with data from the
real worker (GitHub simulated by the acme/shop#7 fixture), served as local previews. That check
found one layout bug, double-spaced code lines, which is fixed.

## Security

| Property | How | Pinned by |
|---|---|---|
| **Off by default** | Without `VERIREVIEW_DASHBOARD_TOKEN`, every `/dashboard` URL answers 404 | `test_dashboard_does_not_exist_without_a_token`; container check |
| Operator sign-in | Constant-time token comparison; the cookie holds an expiry and an HMAC under a key derived from the token, **never the token**. Rotating the token ends all sessions | `test_session_round_trip_and_expiry`, `test_tampered_or_foreign_sessions_are_rejected`, `test_cookie_value_never_contains_the_token` |
| Cookie flags | `HttpOnly`, `SameSite=Strict`, `Path=/dashboard`, `Secure` over HTTPS, 8-hour lifetime | `test_right_token_sets_a_strict_http_only_cookie` |
| Brute force | 10 failed sign-ins per client per 5 minutes, then 429 | `test_repeated_failures_are_rate_limited` |
| XSS from repository content | Jinja2 autoescape everywhere, no `\|safe`, `StrictUndefined`; no JavaScript at all | `test_hostile_repository_text_is_rendered_as_text` (script/img/HTML in comment, code, diff, explanation) |
| Headers | CSP `default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`, `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, **`Cache-Control: no-store`** (private code) | `test_security_headers_on_every_dashboard_response` |
| Read-only | Only GET pages; the POSTs are sign-in and sign-out. Queries never write | code review; `dashboard/queries.py` |
| Path input | Repository names validated (`RepoRef`); ids are integers; unknown ones answer 404 | `test_unknown_or_malformed_addresses_are_not_found` |
| Retention | `verireview purge-audit [--days N]` sets the stored case to SQL NULL for rows older than the retention; verdict, hashes and evidence stay (the audit trail) | `test_retention_removes_stored_code_but_keeps_the_verdict` |

Anyone with the token sees every repository of every installation. That fits one operator, not
a team. Per-user access through GitHub OAuth was the alternative, and is noted under limitations.

## Running it

```bash
# .env (never committed): VERIREVIEW_DASHBOARD_TOKEN=<long random value>
docker compose up -d --build
# open http://localhost:8000/dashboard and sign in with the token
uv run verireview purge-audit              # e.g. daily, from cron or a scheduler
```

Real output of the retention command on the local database:

```text
removed stored code from 0 audit row(s) older than 90 day(s)
```

## Limitations

- **One shared token.** There are no per-user accounts or per-repository permissions, and no audit
  of who viewed what. For several people, GitHub OAuth with repository access checks would be the
  next step.
- **No live data yet.** Rows come from the App's worker, and the live App run is still pending (the
  Phase 11 guide). Until then the dashboard is empty, or holds test data.
- **Evidence text keeps short code quotes** after the retention purge (e.g. "Added condition
  `not username`"). Only the full case (code files, diff, thread) is removed.
- **The purge must be scheduled by the operator.** Nothing runs it automatically.
- **Plain pages.** There are no search, filters or pagination beyond the latest 100 jobs.
