# ADR-003: When VeriReview may fail a check (the enforcement gate)

- **Status:** Accepted (owner decisions, 2026-09-24)
- **Date:** 2026-09-24
- **Phase:** 12

## Context

The roadmap's Phase 12 allows enforcement "only for categories whose measured FAR on the frozen
test set is below an agreed threshold (e.g. ≤ 5%), per-repository opt-in, default advisory".

The best evidence available is the one blind run on benchmark v2
(`experiments/phase10_1_test.json`). It has 10 bad resolutions per category (3 for `other`) and
per-category false acceptance of 0–30%. A point estimate of 0/10 says little: its one-sided 95%
upper bound is 26%.

A merge-blocking verifier that is wrong 1 time in 7 would teach developers to ignore it, or would
block correct work.

## Options considered

1. **Gate on point estimates ≤ 5%.** Naming (0/10) would qualify today. That rests on 10 cases,
   and it ignores false blocking.
2. **Gate on 95% upper bounds ≤ 5%** for both false acceptance and false blocking, per category,
   on a frozen pre-registered test run. Strict: it needs at least 59 bad and 59 good cases per
   category with no errors. Nothing qualifies today.
3. **Upper bounds ≤ 10%.** A looser version of option 2; it needs at least about 29 clean cases per
   class.
4. **No enforcement code at all** until the data exists.

## Decision

- **Option 2.** The gate is computed by `verireview enforcement-eligibility` from a frozen test
  report and shipped as `src/verireview/enforcement/eligibility.json`. A test pins that the
  shipped file equals the recomputation. Today it admits **no category**.
- **The machinery is built but inert** (owner decision: "gated machinery, inert"), with four
  independent locks. All four must be open before a check fails:
  1. the global `VERIREVIEW_POLICY_ALLOW_BLOCK` (off);
  2. the repository has been promoted to `enforcement`. Promotion is one stage at a time, needs
     at least 14 days of human review with at least 10 reviewer confirmations, and every change
     is recorded;
  3. every failed requirement is in an enforced category that is eligible *now*. If eligibility
     is later withdrawn, enforcement stops without touching the repository settings;
  4. the repository owner has made the check **required** in branch protection. This lock is
     outside VeriReview.
- **What "enforcement" does:** the check concludes `failure` (owner decision: "failed check, the
  repository decides"), and only for NOT_SATISFIED at MEDIUM confidence. Everything else stays
  neutral.

## Consequences

- Nothing blocks today, whatever the settings: the category lock is closed by the evidence, and
  repositories without an opt-in are clamped to human review.
- Opening the gate needs a larger frozen test set and better rules. At least 59 bad and 59 good
  cases in a category, with at most a handful of errors, is out of reach at the current 10–30%
  per-category error rates. It should come with human labels (Phase 9's open item).
- When a new frozen test run exists, regenerate the file with
  `enforcement-eligibility REPORT --write`. The pin test then compares it with that report.
- `VerificationResult` gained `RequirementStatus.category` (result schema v2), so the policy can
  check categories per requirement rather than per case.
