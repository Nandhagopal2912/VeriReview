# Phase 1: GitHub Ingestion

**Goal:** given a PR and a review comment, reconstruct the review thread and its temporal
resolution window, then emit a `ReviewCase` (see `src/verireview/contracts/review_case.py`).

## Data flow

```text
verireview ingest OWNER/REPO PR --comment-id ID
  │
  ├─ GET  /repos/{r}/pulls/{n}                  → PR (title, base/head SHA)
  ├─ POST /graphql  reviewThreads               → isResolved / resolvedBy   (token only)
  ├─ GET  /repos/{r}/pulls/{n}/comments         → flat review comments
  │        └─ threads.reconstruct_threads()     → ReviewThread (root + replies)
  ├─ GET  /repos/{r}/issues/{n}/timeline        → force-push events
  ├─ GET  /repos/{r}/pulls/{n}/commits          → ordered commits (max 250)
  │        └─ ingestion.build_window()          → ResolutionWindow + flags
  ├─ GET  /repos/{r}/pulls/{n}/files            → the PR's own files (base-drift filter)
  ├─ GET  /repos/{r}/compare/{start}...{end}    → files changed in the window
  │        (fallback: the PR's files when start is unreachable)
  ├─ GET  /repos/{r}/contents/{path}?ref=start  → before_code
  │        └─ locate_comment_line()             → anchor_line (from diff_hunk text)
  ├─ GET  /repos/{r}/contents/{path}?ref=end    → after_code (+ changed test files)
  │        └─ make_unified_diff()               → unified_diff
  └─ ReviewCase → JSON file / stdout and PostgreSQL (review_cases + normalised tables)
```

## API facts the design depends on

These are based on GitHub's documented behaviour. **Check them against live data** (see below).

| # | Fact | Consequence in code |
|---|---|---|
| F1 | Thread resolution (`isResolved`, `resolvedBy`) is **GraphQL-only**, and GraphQL requires a token. | Without a token: `is_resolved=None`, flag `resolution_state_unknown`. |
| F2 | No resolution **timestamp** is exposed. | Window ends at PR head; flag `resolution_time_unknown`. Webhooks (Phase 11) will give exact times. |
| F3 | Review comment ids can exceed 32 bits; GraphQL `databaseId` is Int32. | Use GraphQL `fullDatabaseId` to match REST ids. DB columns are `BIGINT`. |
| F4 | REST replies carry `in_reply_to_id` = the root comment. | Grouping by root; reply-to-reply chains are followed defensively. |
| F5 | `original_commit_id` is the commit the reviewer saw; `commit_id` moves with later pushes. | Window starts at `original_commit_id`. |
| F6 | Commit dates are client-set; there is no push timestamp in the API. | Commit order comes from the PR commit list. Timestamps are only used to exclude commits written before the comment, and as a fallback. |
| F7 | Force-pushes appear as `head_ref_force_pushed` timeline events; old SHAs may disappear from the PR. | `original_commit_not_in_pr`, `history_rewritten`, `ordered_by_timestamp` flags. |
| F8 | The PR commits endpoint returns at most 250 commits. | Flag `commit_list_truncated`. |
| F9 | `line` is `null` for outdated comments; `original_line` stays. | Both stored. |
| F10 | **Live:** `original_line` can disagree with the file at `original_commit_id` (click#2811: off by 3, file byte-identical to the commit). | `anchor_line` is found by matching `diff_hunk` text. Later phases use `anchor_line`, not `original_line`. |
| F11 | **Live:** a rebase resets committer dates but keeps author dates, and `--amend` also keeps the author date. | In rewritten history, "authored before / committed after" commits are `ambiguous_rewritten_commits`, not guessed. |
| F12 | **Live:** compare across a rebase or base merge includes upstream changes (click#2622: 15 unrelated test files). | `ChangedFile.in_pr` via the PR's file list. Only in-PR test files are collected. Flag `base_drift_possible`. |

## Window flags (how reliable a case is)

| Flag | Meaning |
|---|---|
| `resolution_state_unknown` | No token, so we don't know if the thread was resolved. |
| `resolution_time_unknown` | Resolved, but *when* is unknown, so the window extends to PR head. |
| `original_commit_not_in_pr` | Reviewed commit is no longer in the PR's commit list. |
| `history_rewritten` | …and a force-push happened after the comment. |
| `ordered_by_timestamp` | Candidate commits were chosen by committer date (less reliable). |
| `pre_comment_commits_excluded` | Commits after the reviewed one but committed before the comment was written. They can't be responses to it. |
| `no_subsequent_commits` | Nothing was committed after the comment. |
| `commit_list_truncated` | PR has ≥ 250 commits; list may be incomplete. |
| `before_code_unavailable` | File at the reviewed commit could not be fetched. |
| `file_deleted` / `file_renamed` | Commented file was deleted / renamed within the window. |
| `changed_files_from_whole_pr` | Compare failed, so changed files cover the whole PR, not just the window. |
| `ambiguous_rewritten_commits` | Rewritten history contains commits that could be rebased old work or amended responses. |
| `base_drift_possible` | The window includes upstream changes. The diff of the commented file may contain unrelated edits. |
| `anchor_line_mismatch` | `anchor_line` ≠ GitHub's `original_line`. Trust `anchor_line`. |
| `anchor_not_found` | The `diff_hunk` text is not in `before_code`, so the commented code can't be located reliably. |

Later phases should treat a case with `history_rewritten`, `before_code_unavailable`,
`anchor_not_found` or `ordered_by_timestamp` as a candidate for `UNCERTAIN`. With
`base_drift_possible`, only diff hunks near the target symbol should count as evidence.

## Security

- The token is a `SecretStr`, sent only as a header, and is never logged or stored.
- The client only accepts relative API paths, so the token cannot be sent to another host.
- `owner/repo` and commit SHAs are validated. File paths are URL-quoted.
- Commit author e-mails are not modelled and so never stored.
- Every DB row is scoped to a repository (isolation groundwork for Phase 11).

## Running

```bash
docker compose up -d db && uv run alembic upgrade head
uv run verireview threads OWNER/REPO PR                 # list threads + comment ids
uv run verireview ingest  OWNER/REPO PR --comment-id ID --out dataset/raw/case.json
```

Set `VERIREVIEW_GITHUB_TOKEN` in `.env` (fine-grained PAT, read-only, public repos) to enable
resolution state and the 5,000 requests/hour limit. Without it: 60 requests/hour, and each
ingestion uses about 8–10 requests.

## Deferred (tracked, not forgotten)

- **ETag/conditional-request caching.** Not needed for single-PR ingestion. It will be added
  with bulk mining (Phase 9), when rate limits matter.
- **Exact resolution time.** Needs webhooks (Phase 11).
- **Multi-file requirements.** The MVP diffs the commented file only. `changed_files` and
  `test_files` carry the rest.

## Acceptance: live verification (requires the user)

Unit tests run on a synthetic fixture (`tests/fixtures/github/acme_shop_pr7`). The roadmap
target is **≥ 10 hand-checked real threads**, including at least one force-push case and one
multi-commit case. Record each check in `docs/phase1_live_checks.md`.
