# Phase 1: Live Verification Log

**Date:** 2026-09-23 · **Mode:** unauthenticated public REST (no token, so resolution state is
unknown for every case) · **Code:** Phase 1 plus the live-check fixes (schema v2).

Candidates: merged PRs with `review:changes_requested` from GitHub search. One thread per PR:
the first thread on a `.py` file, preferring threads with replies. Responses were cached, and
only real `ingest_review_case` code ran.

## Automated consistency checks (independent of the ingested output)

| Check | Meaning |
|---|---|
| C1 | GitHub's `original_line` in `before_code` equals the diff_hunk's last line (tests GitHub's line number, not ours) |
| C2 | Subsequent commits come after the reviewed commit, in PR order (only when it is still in the PR) |
| C3 | Every subsequent commit is not before the comment; every excluded one is |
| C4 | Diff is non-empty iff the commented file changed in the window |
| C5 | Thread comments are chronological |

## Results: 8 threads ingested, 2 PRs skipped (no Python review threads)

| # | Case | PR commits | Window (subsequent / ambiguous / excluded) | Key flags | anchor vs original_line | C1 | C3 | C4 | C5 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | pallets/click#3460 | 1 | 0 / 1 / 0 | rewritten, drift (27 files) | 25 = 25 | ✅ | ✅ | ✅ | ✅ |
| 2 | pallets/click#2811 | 2 | 2 / 0 / 0 | original not in PR, drift | **1050 ≠ 1053** | ❌ GitHub | ✅ | ✅ | ✅ |
| 3 | pallets/click#2622 | 8 | 6 / 2 / 0 | rewritten, drift (60 files) | 300 = 300 | ✅ | ✅ | ✅ | ✅ |
| 4 | pydantic/pydantic#5235 | 30 | 30 / 0 / 0 | rewritten, drift (50 files) | 1056 = 1056 | ✅ | ✅ | ✅ | ✅ |
| 5 | python-attrs/attrs#759 | 5 | 0 / 0 / 0 (reviewed = last commit) | none | 347 = 347 | ✅ | ✅ | ✅ | ✅ |
| 6 | python-attrs/attrs#620 | 8 | 3 / 5 / 0 | rewritten | **87 ≠ 88** | ❌ GitHub | ✅ | ✅ | ✅ |
| 7 | pytest-dev/pytest#14443 | 2 | 1 / 1 / 0 | rewritten | 1548 = 1548 | ✅ | ✅ | ✅ | ✅ |
| 8 | pytest-dev/pytest#13757 | 2 | 1 / 1 / 0 | rewritten, drift (12 files) | 913 = 913 | ✅ | ✅ | ✅ | ✅ |

C2 applied only to #5; it passed. In the other 7 cases the reviewed commit was no longer in the PR.
Every C1 failure is GitHub's `original_line` disagreeing with the commit's content. `anchor_line`
located the commented code in **8/8** cases.

## Manual semantic spot-checks

- **click#2622.** Comment: "This does not call the new function you created." The diff at
  `anchor_line` 300 changes `self.fail(self.get_missing_message(...))` to
  `self.fail(self.get_invalid_choice_message(...))`. The response is captured. The two commits
  authored in 2023 (before the 2024 comment, rebased later) are correctly `ambiguous`, not responses.
- **pytest#13757.** Comment: "`UsageError` is not quite right here…". The diff replaces
  `raise UsageError(...)` at `anchor_line` 913 with `raise nodes.Collector.CollectError(msg)`
  and removes the import. The response is captured.
- **pydantic#5235.** All 30 "subsequent" commits are authored 1–2 days after the comment:
  the author rebuilt the branch. Classification is correct.
- **attrs#759.** The reviewer commented on the PR's last commit and nothing followed, so
  `no_subsequent_commits` and an empty diff are correct.

## Findings that changed the code

| ID | Finding | Fix |
|---|---|---|
| L1 | Rebases reset committer dates, so old work looked like responses (click#2622) | Classify by author date in rewritten history |
| L2 | Amended responses keep their old author date (click#3460) | `ambiguous_rewritten_commits`. The window still ends at them |
| L3 | Compare across a rebase includes upstream files (click#2622: 15 unrelated test files) | `ChangedFile.in_pr`, drift flag, only in-PR tests collected (15 → 1) |
| L4 | GitHub `original_line` off by 1–3 lines in 2/8 cases | `anchor_line` from diff_hunk text |
| L5 | CLI crashed printing non-ASCII JSON on a Windows console | stdout/stderr reconfigured to UTF-8 |

## Implications for later phases

1. **History rewriting is the norm, not the edge case.** In 7/8 PRs the reviewed commit no longer
   existed in the PR, so the timestamp fallback is the main path.
2. **Base drift inside the commented file is real.** click#2811 shows 83 diff hunks and pydantic#5235
   shows 58, mostly upstream changes. Phase 3 must restrict evidence to hunks near `anchor_line`
   and the target symbol, never the whole-file diff.
3. **Resolution state was unknown for every case** (no token). Verdict logic must not depend on it.

## Status against the roadmap target

- [x] ≥ 1 force-push case (6 cases with `history_rewritten`)
- [x] ≥ 1 multi-commit case (#2622, #5235, #620)
- [ ] **≥ 10 threads: 8 of 10 done.** The unauthenticated budget (60/hour) ran out. The remaining 2
      need either another hour or a read-only token in `.env`.
