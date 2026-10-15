# Threats to Validity

Organised the usual way in empirical software engineering: construct, internal, external and
conclusion validity, plus reliability. For each threat, the section states what was done about it
and what remains. Numbers come from the recorded reports in `experiments/`.

## Construct validity: do we measure what we claim?

- **What "satisfied" means.**
  - A verdict is derived from per-request statuses (`benchmark.labels.derive_verdict`), following
    `docs/annotation_guide.md`.
  - Humans read requests differently. Two annotators agreed on all 15 random cases but on only 5
    of 21 already-disputed ones (κ 0.33 over 36), mostly about whether a comment asks for anything
    at all, and about how much must be done.
  - *Mitigation:* the verdict is derived, not chosen, so a label cannot contradict itself. The 19
    disagreements were adjudicated with written reasons. *Remains:* the guide needs sharper rules
    on exclusion and on partial work.
- **False acceptance as the primary metric.**
  - It captures the costly error (accepting a fix that was not made), not every kind of usefulness.
  - *Mitigation:* false blocking, coverage, selective accuracy and macro-F1 are reported next to it.
- **"Uncertain" counts as wrong in accuracy.**
  - Gold "satisfied" and predicted "uncertain" counts as an error, which understates the value of
    abstaining.
  - *Mitigation:* coverage and selective accuracy are reported separately (v3: coverage 0.57,
    right when decided 0.80).
- **Code-only evidence.**
  - The verifier sees the file after the window. It cannot see discussion outside the thread, CI
    results, or changes in other files.
  - A case whose fix lies elsewhere is out of scope by design, and a human labeller with more
    context may judge it differently.

## Internal validity: could something other than the method explain the results?

- **Same author for rules and authored test cases.**
  - The controlled and adversarial cases were written by the rules' author, though before each
    round's rule changes, from a fixed recipe that the tests check (counts per category, verdict
    mix, difficult-case types).
  - *Remains:* targeting cannot be ruled out. The fresh real-world cases are the independent part.
- **Provisional model labels.**
  - In rounds 1 and 2 the real-world labels were Claude's, written blind before any verifier ran.
    Since Phase 10.2 they are human.
  - Re-scoring the recorded round-2 run (no re-run) changed the picture: the model labels had
    hidden a false acceptance, and later adjudication removed it again.
  - Round 1 real-world labels are still provisional.
- **The second annotator was not independent.**
  - The second annotator was the project owner, who had seen system results.
  - One adjudicated decision was revised on re-check, with knowledge of the system's verdict. The
    revision is recorded as such in `v2/FREEZE_LOG.md` entry 7.
- **Leakage between development and test.**
  - Each test set was frozen by hash before rule changes, run once under a protocol whose hash is
    in the report, then retired to development data.
  - Old rules are re-run from an exact commit (`git archive`) for paired comparison.
  - Thresholds of the similarity baselines come from the development split only.
- **The v3 cases were written after the v2 results were known.**
  - They were not written after an error analysis of the human-labelled v2 cases.
  - The same recipe was kept to limit targeting.

## External validity: does it generalise?

- **Language and scope.** Python only, one commented file per case. Rules follow same-file helpers
  one level deep, with no whole-program control-flow analysis.
- **Projects.**
  - The real-world cases come from 6 open-source projects (httpx, click, pandas, pytest, pydantic,
    Home Assistant), chosen for permissive licences.
  - Industrial code review, other languages and other review cultures may differ.
- **Request mix.**
  - About two thirds of real requests are `other` (refactoring, wording, style).
  - GitHub suggestion blocks are easy to check. They appear in 28 of 60 v2 real-world comments
    but only 12 of 60 in v3, and real-world coverage fell from 0.44 to 0.22. Coverage therefore
    depends on the request mix of the sample.
- **Few bad real-world resolutions.**
  - Most resolved threads were addressed: v3 real-world has 5 not satisfied and 2 partially
    satisfied of 58.
  - Real-world false acceptance therefore rests on very few cases (0 of 7 accepted on v3).
- **Live use.**
  - The GitHub App ran end to end on one private test repository.
  - It has not run on a team's real repositories, under real load, or in a user study with
    developers.

## Conclusion validity: are the statistics sound?

- **Small samples, wide intervals.**
  - The test sets have 120, 147 and 148 cases; v3 false acceptance is 0.088 with a 95% interval
    of [0.02, 0.17].
  - *Mitigation:* every main number carries a percentile bootstrap interval (2,000 resamples,
    fixed seed), and comparisons use a paired bootstrap on identical cases.
- **Cases are not fully independent.**
  - Several threads can come from one pull request: v3 allows at most 3 per PR.
  - The bootstrap resamples cases, not pull requests, so the intervals may be somewhat too narrow.
- **One run per round.** The variance measured is over cases only, not over rule versions or
  annotators.
- **Many comparisons.**
  - The ablation compares 10 systems.
  - Only the pre-registered primary questions are treated as confirmatory; everything else is
    labelled descriptive in the protocols.
- **The enforcement gate.** It uses exact one-sided Clopper–Pearson bounds per category, a
  conservative choice. No category passes, so no claim of safety for blocking is made.

## Reliability: can others repeat it?

- **Deterministic pipeline.**
  - No language model decides, and the same input gives the same verdict.
  - The code model (UniXcoder) is pinned to a revision and is neutral.
- **Verified reproduction.**
  - All three recorded blind test runs were re-run from their recorded commits on 2026-10-14.
  - The recomputed predictions, gold labels and confidences are identical for every case
    (round 1: 120/120, round 2: 147/147, round 3: 148/148), and so are the bootstrap intervals.
  - The frozen source hash of round 3 matches the protocol (`211a02c7…`). See
    [`REPLICATION.md`](../REPLICATION.md).
- **Frozen data.** All test sets and human labels are pinned by hashes in `tests/benchmark/`. Raw
  annotation exports are never edited, and every label change is logged in a `FREEZE_LOG.md`.
