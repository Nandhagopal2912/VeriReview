# Phase 10: Evaluation Protocol (pre-registered)

Written **before** any verifier ran on the test split (benchmark v1,
`dataset/benchmark/manifest.json`). The test run happens once, with exactly this protocol. Anything
changed after seeing test results is reported separately as post-hoc and never replaces these
numbers.

## Data

| Split | Sources | Cases | Labels |
|---|---|---|---|
| dev | `fixtures` (29), `heldout_fixtures` (24), real-world dev (30) | 83 | author-written (fixtures) / provisional model (real-world) |
| **test** | `benchmark/controlled` (60), `benchmark/adversarial` (40), real-world test (20) | **120** | author-written blind (controlled, adversarial) / provisional model (real-world) |

Excluded real-world cases (no requirement, external context) are not evaluated. Results are always
reported **per source** as well as pooled, because the three sources differ in who labelled them
and how.

## Systems (plan §21 ablation)

| Row | System | Plan row | Notes |
|---|---|---|---|
| A | lexical overlap (`added` view) | A keyword/lexical | threshold: Youden's J on the **dev split** (83 cases) |
| B | MiniLM embeddings (`added` view) | B embedding similarity | threshold: Youden's J on dev |
| B′ | UniXcoder (`code` view) | B, code-aware | threshold: Youden's J on dev |
| L | `phase2-locality`: change near the comment | (diff only) | |
| S | `phase3-structure`: AST change in the commented symbol | D without rules | |
| R | `phase4-requirements`: extraction + AST + ambiguity gate | | |
| C/D | `phase5-rules`: rules (which query the AST) | C, D | rules and AST are not separable in this design: every rule queries Tree-sitter facts, so plan rows C and D map to one system |
| E | `phase7-semantic`: rules + AST + UniXcoder evidence | E | verdicts identical to C/D by construction (ADR-002); reported to confirm it |
| **F** | **`mvp`**: full VeriReview | F | + reliability-adjusted confidence. Phase 8b was not done, so F = C/D verdicts |
| F-gold | `mvp` with gold requirements | (diagnostic) | isolates extraction errors |

No system is tuned on test. The rules are frozen at their Phase 5.1 state, plus only the Phase 9b
positional-read fix in `syntax/parser.py`, which does not change any value.

## Metrics

Per system, on the pooled test split and per source:

1. Accuracy, macro-F1 (over classes with support), per-class precision / recall / F1, confusion
   matrix.
2. **False acceptance rate (FAR):** predicted SATISFIED among gold NOT / PARTIALLY. **False blocking
   rate (FBR):** predicted NOT_SATISFIED among gold SATISFIED. These are the existing definitions in
   `evaluation/metrics.py`.
3. **Coverage:** share of cases with a decided verdict (not UNCERTAIN). **Selective accuracy:**
   accuracy on the decided cases. Added because abstaining (UNCERTAIN → human review) is by design,
   and plain accuracy counts it as an error.
4. Accuracy per category (main requirement category) and per adversarial type.
5. For F: accuracy per confidence level (LOW / MEDIUM). There are no numeric probabilities, so no
   ECE (plan §15, §20).

## Uncertainty

- **95% percentile bootstrap intervals** over cases, 2,000 resamples, seed 20260924, for accuracy,
  macro-F1, FAR, FBR and coverage.
- **Paired bootstrap** of the difference F − X in accuracy and FAR for every other system X (same
  resampled cases for both). A difference is called clear only if its interval excludes 0.

## Primary questions (decided in advance)

1. Is F's FAR on test low, and lower than the similarity baselines' (A, B, B′)?
2. Does F beat the ablation rows on accuracy / macro-F1, with the paired interval excluding 0?
3. How does F do on each source, especially real-world, where coverage is expected to be low
   because most requests are `other`?

Everything else is descriptive.

## Procedure

1. Implement `verireview eval-benchmark`. The test split needs an explicit `--final-test-run` flag.
2. Develop and debug **on the dev split only**.
3. Run the test split once and save `experiments/phase10_test.json`, with commit, dataset hashes,
   manifest version and protocol hash.
4. Report the results as they are. Any error analysis on test cases is descriptive only, and fixes
   motivated by it belong to a later phase with a new test set.
