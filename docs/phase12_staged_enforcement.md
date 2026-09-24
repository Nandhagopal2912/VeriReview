# Phase 12: Staged Enforcement (built, gated, inert)

Phase 12 adds what the plan calls selective enforcement: a path by which VeriReview could one day
fail a pull-request check for the kinds of requests it verifies reliably. **The evidence does not
support enforcing anything yet**, so the path is built with every lock in place and nothing ever
blocks. The rule is recorded in [ADR-003](adr/003-enforcement-gate.md).

Owner decisions (2026-09-24):

- **Scope:** build the gated machinery; leave it inert.
- **Gate:** the one-sided 95% upper bound of both false acceptance and false blocking must be
  ≤ 5% per category, on a frozen test run.
- **Effect when enforced:** a *failed* check, which blocks merging only if the repository makes
  the check required.

## The evidence today (real output)

`verireview enforcement-eligibility experiments/phase10_1_test.json --write`, on the one blind v2
run of Phase 10.1:

```text
F on experiments/phase10_1_test.json (split test, manifest v2, protocol e3a7f5e68d6e); gate: one-sided 95% upper bounds <= 0.05
category         bad  FA  FAR up  good  FB  FBR up  eligible
naming            10   0   0.259    10   0   0.259  no
validation        10   3   0.607     6   1   0.582  no
testing           10   2   0.507    16   1   0.264  no
error_handling    10   2   0.507     9   1   0.429  no
api_behavior      10   1   0.394     6   0   0.393  no
other              3   0   0.632    33   0   0.087  no
eligible: none
```

Even naming, with no errors, cannot show it stays below 5%: with 10 cases, a true error rate of up
to 26% is still consistent with seeing none. A category needs at least 59 bad and 59 good cases
without errors to pass, which is several times the current benchmark. The other categories also
have to become more accurate first.

## Stages

```text
observe ──► advisory ──► human_review ──► enforcement
audit only  neutral check  + "Confirm reviewed"  may fail the check (eligible categories only)
```

| Rule | Where | Pinned by |
|---|---|---|
| A repository without an opt-in runs at the global default, **clamped to human review** | `enforcement/stages.effective_policy` | `test_repository_without_opt_in_never_enforces`, Phase 11 `test_check_stays_neutral_even_if_blocking_were_configured` |
| Promotion **one stage at a time**; rollback to any stage at any time | `change_stage` | `test_promotion_is_one_step_at_a_time_and_recorded`, `test_rollback_is_always_allowed` |
| Entering enforcement needs **≥ 14 days** of human review with **≥ 10 reviewer confirmations**, and only **eligible** categories | `change_stage` (`VERIREVIEW_ENFORCEMENT_MIN_*`) | `test_enforcement_needs_time_and_confirmations_in_human_review`, `test_enforcement_is_refused_without_eligible_categories` |
| Every change records actor, reason, from, to and categories (append-only) | `repository_policy_changes` | `test_promotion_is_one_step_at_a_time_and_recorded` |
| Enforced categories are cut to the eligibility **at every job**; withdrawing eligibility stops enforcement | `effective_policy` | `test_enforced_categories_are_cut_to_current_eligibility` |

The human-review stage puts a **Confirm reviewed** button on the neutral check. Pressing it sends a
signed `check_run`/`requested_action` webhook. The reviewer's login is recorded once per head
commit and listed on the check. The confirmations count towards promotion. They do not change a
verdict.

## When a check may fail

`BLOCK` (from the policy) and a `failure` conclusion (on the check) need **all** of:

1. `VERIREVIEW_POLICY_ALLOW_BLOCK=true` (global, off by default: `test_default_configuration_never_blocks`);
2. the repository at the `enforcement` stage;
3. verdict NOT_SATISFIED at MEDIUM confidence, **and every failed requirement's category**
   enforced for the repository and eligible now. `RequirementStatus.category` (result schema
   v2) carries it. A mixed or unknown category gives a warning, not a block
   (`test_category_lock_blocks_only_when_every_failed_requirement_is_enforced`).

The fourth lock is the repository's branch protection: a failed check blocks merging only if the
check is required. `test_any_closed_lock_keeps_the_check_neutral` runs the whole worker with each
lock closed in turn (no opt-in, human-review stage, global switch off, category not eligible), and
`test_check_fails_only_with_every_lock_open` covers the one configuration that fails. That
configuration uses a pipeline double, because today's eligibility never allows it.

## Operating it (real output)

```text
$ verireview repo-policy show demo/shop --installation 1
demo/shop: no opt-in (runs at the global default, at most human_review)
$ verireview repo-policy set demo/shop --installation 1 --stage enforcement --categories naming --actor owner --reason "try to skip straight to enforcement"
refused: promote one stage at a time: advisory → human_review, not enforcement
$ verireview repo-policy set demo/shop --installation 1 --stage human_review --actor owner --reason "start the human-review stage"
demo/shop: stage human_review since 2026-09-24 (by owner); enforced categories: -; confirmations since: 0; global blocking switch: off
$ verireview repo-policy set demo/shop --installation 1 --stage enforcement --categories naming --actor owner --reason "enforce naming after review"
refused: not eligible on the frozen test evidence: naming (eligible now: none)
```

(A demo repository on the local database; its rows were removed afterwards.)

## What would open the gate

1. A larger frozen test set: at least 59 bad and 59 good resolutions for any category considered,
   ideally with human labels (Phase 9's open item).
2. Rules accurate enough to make almost no errors on it, in both directions.
3. One pre-registered run. Then
   `verireview enforcement-eligibility REPORT --write`, a code review of the regenerated file, and
   the per-repository promotion above.

## Limitations

- **Case-level categories in the gate.** Eligibility is measured per case (its main requirement's
  category), while the policy checks every failed requirement. For multi-requirement cases the two
  differ. The policy side is the stricter one.
- **Confirmations are not a security boundary.** GitHub offers check-run buttons to users who can
  see the check. The login is recorded, not checked against repository permissions, and the count
  only feeds the promotion rule.
- **No time-based demotion.** A repository in enforcement stays there until someone demotes it,
  unless its categories lose eligibility.
