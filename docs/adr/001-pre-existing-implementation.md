# ADR-001: Verdict when the requested behaviour already existed before the comment

- **Status:** Proposed (awaiting project owner's decision)
- **Date:** 2026-09-23
- **Phase:** 2 (required by plan §18: "Define explicitly … Document the chosen policy.")

## Context

Sometimes a reviewer asks for something the code already does: the reviewer misread the diff, or
the check lives a few lines away. Example fixture `validation-003-already-present`: the reviewer
asks "Please validate that `quantity` is positive", but `if quantity <= 0: raise ValueError`
is already on line 2 and nothing changes afterwards.

The plan's core question is ambiguous here:
*"Did the subsequent code changes actually satisfy the review requirement?"*
No subsequent change did anything, but the final code meets the requirement.

## Options considered

1. **SATISFIED, based on the final code (with `already_present` evidence).** Judge the code at the
   end of the window against the requirement. Record an explicit `already_present` evidence
   item and cap confidence at MEDIUM.
   - Pro: answers what enforcement actually needs to know, i.e. is resolving this thread
     legitimate. A reviewer's misreading should not block a merge.
   - Pro: one consistent rule for every case (always judge the final state).
   - Con: "satisfied" without any change can look odd, so the evidence must say why.
2. **UNCERTAIN, sent to human review.** Treat it as a possible reviewer/developer misunderstanding.
   - Pro: conservative.
   - Con: adds noise to human review for a situation evidence can settle. It also mixes up
     "we can't tell" with "we can tell, but it's unusual".
3. **A fifth verdict (e.g. `ALREADY_SATISFIED`).**
   - Con: changes the four-verdict contract (plan §4) and every metric, for a rare case.

## Decision (recommended)

**Option 1.** Verification judges the code at the end of the resolution window. When the
requirement holds and the relevant code was not changed after the comment, the verdict is
`SATISFIED`, confidence at most `MEDIUM`, with an `already_present` evidence item. The
policy layer (Phase 8) may still route `already_present` cases to `HUMAN_REVIEW` if the team
wants.

## Consequences

- Fixtures with `hard_case: pre_existing` are labelled `SATISFIED`.
- Phase 5 rules must evaluate `after_code` (not only the diff) and emit `already_present`
  when the satisfying construct also exists in `before_code`.
- The Phase 2 locality baseline gets these cases wrong (it predicts NOT_SATISFIED), which is expected.
- If the owner chooses Option 2 instead: relabel `validation-003-already-present` to
  `UNCERTAIN` and change this ADR's decision. No code is affected yet.
