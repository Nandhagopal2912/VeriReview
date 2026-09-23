# ADR-002: Code-model evidence is neutral until the benchmark can justify more

- **Status:** Proposed (Phase 7; to be confirmed by the project owner)
- **Date:** 2026-09-23
- **Phase:** 7 (feeds Phase 8b)

## Context

Phase 7 adds a code-aware model (UniXcoder) as an evidence source. The plan says the semantic
model is "one evidence source, never the final authority" (plan §2, §14), and the roadmap
defers weighting to Phase 8b. It does not say what the evidence may do in the meantime.

The measurements (docs/phase6_nlp_baselines.md, docs/phase7_code_model.md) show:
- relevance separates valid from invalid resolutions only weakly (evidence stage ROC-AUC dev 0.57,
  held-out 0.74). Used as a decision at the dev-tuned threshold it would accept 2 of 8 invalid
  held-out fixes (false acceptance 0.25) and reject 5 of 14 valid ones (0.36), against 0 and 0.07
  for the rules;
- invalid fixes are often highly relevant: the right check in the wrong place
  (`validation-002`, 0.73) or a log line whose string repeats the request (`validation-004`,
  0.71);
- the dev set has **no** case where the rules are undecided but the gold answer is SATISFIED, so
  there is no dev data on which Phase 8b could tune a rule like "relevance ≥ τ turns UNCERTAIN into
  SATISFIED". The held-out set has two, and it must not be used for tuning.

## Options considered

1. **Neutral evidence (`passed=None`), not read by any aggregator.** It is shown in the explanation
   with its location. Verdicts are exactly the rules'.
   - Pro: cannot raise false acceptance (pinned by tests and the injection suite).
   - Pro: a human reviewer sees which added code the model links to each requirement.
   - Con: no accuracy gain in this phase.
2. **Tie-breaker for rule-inconclusive requirements** (relevance ≥ τ → SATISFIED).
   - Con: τ cannot be tuned on dev (no such dev cases), so it would be guessed or tuned on held-out.
   - Con: the measured false acceptance at usable thresholds breaks the FAR = 0 property.
3. **Veto** (low relevance turns SATISFIED into UNCERTAIN).
   - Con: `validation-003` / `h-testing-already-covered` (ADR-001, nothing added) score 0 and would
     be vetoed wrongly; it would raise false blocking for no measured gain.

## Decision

**Option 1.** `semantic_relevance` evidence is neutral. The `phase7-semantic` pipeline uses the
MVP aggregator unchanged, and tests pin "verdicts identical to `mvp`" on dev and held-out. The
default pipeline stays `mvp`, so the service does not need the model.

## Consequences

- Phase 8b may give the evidence a role only after the Phase 9 benchmark provides dev cases where
  rules are inconclusive, and only if held-out false acceptance stays 0.
- The most defensible future role is **ordering the human-review queue** (which inconclusive
  requirement looks addressed), not changing verdicts.
- Revisit if a fine-tuned or instruction-following model (D8) is evaluated.
