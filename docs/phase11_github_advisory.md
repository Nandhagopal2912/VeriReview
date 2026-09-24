# Phase 11: GitHub Advisory Mode

> **Update, Phase 12:** the check is still always `neutral` by default. Phase 12 added a gated
> path to a `failure` conclusion that needs four locks open, none of which is open today (a
> repository opt-in, the global blocking switch, an eligible category, and the repository's
> branch protection). See [phase12_staged_enforcement.md](phase12_staged_enforcement.md).

VeriReview now runs as a GitHub App. When a review thread is resolved on a pull request, it checks
whether the code changes made after the comment actually address it. The result appears as a
**"VeriReview" check whose conclusion is always `neutral`**. The check never fails and never blocks
a merge. It is a pointer for reviewers. The Phase 10.1 numbers (accuracy 0.65, false acceptance
0.15 on the blind v2 test) do not justify more.

Owner decisions (2026-09-24):

- **Output:** a Check Run, always neutral. No replies in review threads.
- **Trigger:** a thread being resolved. "Re-run" on the check re-verifies every resolved thread of
  the PR. New pushes do not re-trigger it.
- **Live test:** offline in this phase. The live end-to-end check on a real test repository
  follows the guide below once the owner has created the App.
- **New runtime dependency:** PyJWT with its crypto extra (cryptography), for the App's RS256 JWT.

## How it works

```text
GitHub ──webhook──► POST /github/webhook ──► advisory_jobs ──► worker ──► GitHub API
  (signed)          signature check first      (PostgreSQL)     │           check run (neutral)
                    → validated task            one row per      ├─ installation token: 1 repo,
                    → 202 within ms             delivery         │  contents/PR read, checks write
                                                                 ├─ ingest thread (Phase 1)
                                                                 ├─ verify (mvp-2) + policy
                                                                 └─ verification_audit row
```

| Piece | File | What it does |
|---|---|---|
| Webhook endpoint | `api/webhooks.py` | Checks the size limit, then **HMAC-SHA256 over the raw body** (constant-time), then parses. Answers 401 on a bad or missing signature, 503 if no secret is configured. Queues work and returns 202 |
| Events | `advisory/webhooks.py` | `pull_request_review_thread`/`resolved` becomes one thread task; `check_run`/`rerequested` on our own check becomes a whole-PR task. Everything else is ignored. Only ids are taken from the payload, and they are validated |
| Queue | `advisory/jobs.py`, `advisory_jobs` table | Unique `(delivery_id, task_index)` means a redelivery queues nothing. Workers claim with `FOR UPDATE SKIP LOCKED`. Retries back off 30 s, 60 s, 120 s, up to 3 attempts, then the job fails |
| App auth | `advisory/auth.py` | RS256 JWT (9 min), then an **installation token narrowed to the job's repository** with `contents: read`, `pull_requests: read`, `checks: write`. Tokens are cached in memory until 5 min before expiry |
| Worker | `advisory/worker.py`, `verireview worker` | Re-reads the PR and thread from GitHub (never from the webhook body), verifies, applies the policy, audits, and publishes. In `observe` mode it audits only |
| Check Run | `advisory/checks.py` | One check per head commit, updated rather than duplicated. `conclusion` is the constant `neutral`. Untrusted text appears only inside a fenced `text` block |
| Audit trail | `verification_audit` table | Per verification: installation, repository, PR, comment, head SHA, **sha256 of the exact ReviewCase verified**, pipeline version, verdict, confidence, action, full result with evidence |

### What a check looks like (real output)

Offline run: signed `thread_resolved.json` → `POST /github/webhook` → queue → worker, with GitHub
replaced by the recorded acme/shop#7 fixture:

```text
webhook: 202 {'status': 'queued', 'jobs': 1}
worker took a job: True
check: VeriReview completed neutral 4444444
---- title
1 resolved thread(s) checked: 1 satisfied
---- summary
**Advisory only.** This check never fails and never blocks merging. VeriReview checks whether each resolved review thread was actually addressed, from the code changed after the comment. On its latest blind benchmark it was right about 2 times in 3 and accepted about 1 in 7 unaddressed threads, so use it as a pointer for reviewers, not as a gate.

| Thread | Result | Confidence | Suggested |
|---|---|---|---|
| [comment 5001](https://github.com/acme/shop/pull/7#discussion_r5001) | ✅ SATISFIED | MEDIUM | no action needed |

Pipeline `mvp-2`. Details per thread below; evidence lines cite the file, lines and commit they are based on.
---- text
### Comment 5001: SATISFIED (MEDIUM)
```

The `text` part then holds the plan §16 explanation (review request, requirements, 14 evidence
lines with file, lines and commit, result, confidence) inside a fenced block. The webhook payload
used here carries a prompt-injection text, a link and an @-mention in its comment body. None of
them appears in the check, because the worker re-reads the comment from GitHub and the payload
body is never used for content.

## Security properties (plan §22, §30)

| Requirement | How | Pinned by |
|---|---|---|
| GitHub App authentication | JWT → installation token; the PAT stays only for the CLI | `tests/unit/advisory/test_auth.py` |
| Least privilege | App permissions: Checks write, Contents read, Pull requests read, Metadata read. Each token is narrowed further to one repository | `test_installation_token_is_scoped_to_one_repository_and_least_privilege` |
| Webhook signature validation | HMAC-SHA256 of the raw body, `hmac.compare_digest`, checked **before** parsing; no secret means everything is refused | `test_webhooks.py`, `test_webhook_api.py`, integration `test_forged_webhook_is_rejected_and_queues_nothing` |
| Idempotent processing | Unique delivery id; a redelivery returns `duplicate` and queues nothing | `test_duplicate_delivery_is_processed_once` |
| Repository isolation | Per-repository tokens; every audit query filters installation + repository | `test_audit_results_are_isolated_by_installation_and_repository` |
| Secret management | Key file mounted as a Docker secret (`secrets/`, git-ignored). Secrets are `SecretStr` and never logged or stored; the job error text is the exception class plus API path | `test_no_key_or_token_reaches_the_logs`, `test_github_outage_is_retried_later_without_leaking_the_token` |
| Never blocks | `CONCLUSION = "neutral"` constant, independent of policy; `enforcement` + `allow_block` still publish neutral | `test_conclusion_is_pinned_to_neutral`, `test_check_stays_neutral_even_if_blocking_were_configured`, `test_default_configuration_never_blocks` |
| Untrusted content | Payload text is not used; repository text is rendered only inside a fence (a fence inside it is broken); names and SHAs are validated | `test_untrusted_text_only_appears_inside_a_fenced_block`, `test_malicious_repository_name_is_rejected` |
| Failure handling | GitHub outages, rate limits and auth errors are retried with backoff; a missing PR or thread fails at once | `test_github_outage_is_retried_later…`, `test_unknown_thread_fails_permanently` |
| Audit trail | `verification_audit` with an inputs hash and the full result | `test_resolved_thread_ends_as_one_neutral_check_with_an_audit_row` |
| Human-review fallback | UNCERTAIN / PARTIALLY_SATISFIED / low confidence → "human review" in the check | policy tests (Phase 8a) |

Roadmap targets:

- **Done (offline):** a forged webhook is rejected, and a duplicate delivery is processed once.
- **End to end:** done offline, through the real endpoint, queue, worker, audit and check-run
  code, with GitHub simulated. The run on a real test repository is pending the App setup below.

## Running it

Offline, with nothing from GitHub:

```bash
docker compose up -d --build
uv run pytest -m integration tests/integration/test_advisory.py
```

### Live setup (when you want to connect a real repository)

1. **Create a GitHub App.** Go to GitHub → Settings → Developer settings → GitHub Apps → New.
   - Name: e.g. `verireview-<you>`.
   - Webhook: active. URL: your tunnel URL (step 5) followed by `/github/webhook`. Secret: a long
     random string.
   - Repository permissions: **Checks: Read and write**, **Contents: Read-only**, **Pull
     requests: Read-only**. Metadata: Read-only is mandatory. Nothing else.
   - Subscribe to events: **Pull request review thread** and **Check run**.
   - Where can it be installed: only on this account.
2. **Generate a private key** on the App page and save it as `secrets/github-app.pem`. The
   `secrets/` folder is git-ignored. Never paste the key into chat or `.env.example`.
3. **Fill in `.env`** (never committed): `VERIREVIEW_GITHUB_APP_ID=<id>` and
   `VERIREVIEW_GITHUB_WEBHOOK_SECRET=<the secret>`.
4. **Install the App** on one private test repository ("Only select repositories"), then start
   the stack:

   ```bash
   docker compose --profile advisory up -d --build
   ```

   This starts the API on :8000 and a worker that uses the key file as a Docker secret.
5. **Expose the webhook locally**, for example with `npx smee-client --url
   https://smee.io/<channel> --target http://localhost:8000/github/webhook`. Note that smee
   relays the webhook payloads through a third-party service; that is acceptable for a test
   repository.
6. **Try it:** open a PR that changes a Python file, comment on a line ("Please validate
   `username` is not empty"), push a fix, and resolve the thread. A neutral "VeriReview" check
   appears on the head commit within seconds. "Re-run" re-verifies every resolved thread.
7. **Replay a delivery locally** while testing, if needed:
   `uv run verireview replay-webhook payload.json --event pull_request_review_thread`. This signs
   the payload with your secret and only posts to localhost.

Set `VERIREVIEW_POLICY_MODE=observe` to audit without posting anything.

## Limitations

- **Advisory quality only.** About 1 in 7 unaddressed threads is reported as satisfied (v2 test).
  The check says so in its first line.
- **One check per head commit.**
  - A new push does not re-verify; "Re-run" does, on the latest head.
  - Unresolving a thread does not remove it from the check.
- **Not measured live yet.** The worker is a single process by default; several are safe
  (`SKIP LOCKED`), but none has been load-tested.
- **The audit trail grows without a retention policy** (to decide before any real deployment).
- **GitHub Enterprise:** set `VERIREVIEW_GITHUB_API_URL`. Untested.
- **Python files only**, as before. Threads on other files end as UNCERTAIN (human review).
