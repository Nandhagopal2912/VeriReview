# Related Work and What Is New in VeriReview

This literature check was done on 2026-10-14 with web searches, so it is not a systematic review.
Every claim below about another work comes from that work's paper, page or documentation, linked
in **Sources**. Re-check the closest work (Sun et al. 2025) before a formal submission, in case a
newer version exists.

## 1. Closest work: checking whether review comments were addressed

| Work | What it does | How it decides | Evaluation |
|---|---|---|---|
| **Sun et al. 2025**, "Does AI Code Review Lead to Code Changes?" (arXiv 2508.18771) | Measures whether AI-generated (and human) review comments on GitHub led to code changes | A two-stage **LLM** judge (best: gpt-4.1 and o3-mini). Stage 1: is the comment valid? Stage 2: Valid-Fully / Partially / Unaddressed / Uncertain. Input: the reviewed code and a **textual diff** (difflib) up to the merge commit | 150 hand-annotated comments: 86.1% accuracy (6 classes). Human–human κ 0.67–0.76. Models were chosen on the same 150 comments. No AST analysis, no discussion of prompt injection |
| **GitHub Copilot code review**, auto-resolution (changelog, Sept 2026) | Resolves a **Copilot-authored** comment when a later commit addresses it | Not disclosed | No numbers published |
| **CodeRabbit**, request-changes workflow (docs) | On its next review, resolves **its own** open threads that new commits addressed | Not disclosed (LLM-based reviewer) | No numbers published |
| Bosu, Greiler, Bird 2015 (MSR, Microsoft); Rahman, Roy, Kula 2017 (RevHelper, MSR) | Predict whether a review comment is *useful* | Usefulness labelled partly by a **heuristic**: the comment led to a change in nearby lines | Classifiers on comment text and reviewer features (RevHelper: 66% accuracy) |
| Beller et al. 2014 (MSR), "Which problems do they fix?" | Taxonomy of changes caused by review | Manual classification of more than 1,400 changes | 7–35% of review comments are discarded; 75:25 maintainability to functional |

## 2. Related but different tasks

- **Generating the fix, not checking it.**
  - Tufano et al. 2021 (ICSE) and CodeReviewer (Li et al. 2022, ESEC/FSE) learn to produce
    the revised code from a review comment (up to 31% correct in Tufano et al.).
  - Google's ML-based comment resolution (2023) suggests edits that address a comment; about
    52% of comments at 50% precision offline.
  - These systems *produce* a fix. None of them verifies that a human's fix satisfies the
    comment.
- **Comment–code consistency.** Panthaplackel et al. 2021 (AAAI) detect, at commit time, when a
  *code comment* (docstring) becomes inconsistent with changed code. That is a different object
  from a reviewer's request.
- **Structural change analysis.** ChangeDistiller (Fluri et al. 2007) and GumTree (Falleri et
  al. 2014; 2024) compute fine-grained AST edit scripts. VeriReview also works on syntax trees
  (Tree-sitter), but it queries *facts* (guards, handlers, responses, tests) against a
  requirement, rather than producing an edit script.
- **Evaluation of LLM review tools.**
  - RovoDev at Atlassian (2026) reports that 38.7% of generated comments led to code changes,
    against 44.5% for human comments.
  - CRScore (2024), HalluJudge (2026) and CRJudgeBench (2026) judge the quality or validity of
    review *comments*, not whether a later change satisfied them.
- **Prompt injection in review agents.** 2026 reports ("Comment and Control"; Microsoft on the
  Claude Code GitHub Action; Cloudflare on deceptive code comments) show LLM review agents can be
  steered by PR titles, comments and code comments.
- **Methodology.** Registered reports (MSR, ESEM, SANER with *Empirical Software Engineering*)
  pre-register the study design before data collection, to prevent hypothesising after the
  results are known.

## 3. What is new in VeriReview, and the evidence for each point

The task (has a review comment been addressed?) is **not** new: Sun et al. 2025 define almost the
same four outcomes, and Copilot and CodeRabbit resolve their own threads. The claims below are
about *how* VeriReview verifies and *how* it was evaluated. Each points to the part of this
repository that demonstrates it.

1. **Deterministic, request-level verification over program structure, with cited evidence.**
   The closest work asks an LLM to read a textual diff. VeriReview splits a comment into atomic
   requests and checks each one with a category rule over Tree-sitter facts (guards, handlers,
   responses, tests, suggestion blocks). Every verdict cites file, lines and commit, and the same
   input always gives the same output.
   *Evidence:* `rules/`, `syntax/`, `explanations/`; worked example in the README.
2. **Built for "looks fixed but isn't".** The benchmark has an adversarial split of traps:
   - a fix only in a comment, or only in dead code;
   - the right check in the wrong place, or the wrong value;
   - a test file that is never collected.

   False acceptance is the primary metric, and the system abstains (*uncertain*) instead of
   guessing.
   *Evidence:* v3 test FAR 0.088 against 0.70–0.98 for structural, code-model and
   change-location baselines (`docs/phase10_3_rules_v3.md`); adversarial accuracy 0.87.
3. **Works on any reviewer's comments.** Copilot and CodeRabbit document resolving only the
   threads they wrote. VeriReview verifies human reviewers' requests on real open-source pull
   requests.
   *Evidence:* 6 approved repositories, real-world test cases labelled by humans
   (`dataset/benchmark/v3/real_world`).
4. **Measured robustness to prompt injection.** Repository text is treated only as data, and no
   model decides. Planted instructions (code, tests, replies, commit messages, PR titles) changed
   **0 of 2,576** outcomes, while a lexical baseline flipped 6. The closest work does not discuss
   injection, and 2026 reports show LLM review agents are vulnerable to it.
   *Evidence:* `evaluation/injection.py`, `tests/benchmark/test_prompt_injection.py`.
5. **Pre-registered, frozen, paired evaluation, repeated three times.** Each test set is frozen
   by hash *before* the rules change, then run once under a protocol whose hash is recorded,
   old rules against new on the same cases (paired bootstrap). Neither rules nor thresholds are
   ever chosen on the test data. In contrast, the closest work selected its models on its
   annotated sample. This is the registered-report idea applied inside one project.
   *Evidence:* `docs/phase10_protocol.md`, `phase10_1_protocol.md`, `phase10_3_protocol.md`;
   `FREEZE_LOG.md` files; `compare-reports`.
6. **Statistically gated, staged enforcement.** A category may only block a merge when the
   one-sided 95% Clopper–Pearson upper bounds of both its false-acceptance and false-blocking
   rates are ≤ 5% on a frozen run. Blocking also needs a global switch, a repository promoted
   step by step through human review, and branch protection. The tools above resolve threads
   without published error rates.
   *Evidence:* `enforcement/`, ADR-003; today the gate admits no category.
7. **Two empirical findings.**
   - (a) Rule fixes tuned on development data barely transfer: 11 dev cases fixed, 2 of 148
     blind-test verdicts changed.
   - (b) Human labels are the ceiling on hard cases. Two annotators agreed on 15 of 15 random
     cases but only 5 of 21 already-disputed ones (κ 0.33 overall). Sun et al. report κ
     0.67–0.76 on a sample without such a bias toward disputed cases.

   *Evidence:* `docs/phase10_3_rules_v3.md`; `docs/phase10_2_human_labels_v3.md` §3.

**Wording to use:** "To our knowledge, VeriReview is the first to combine deterministic,
structure-based, request-level verification of human review comments with measured
prompt-injection robustness and a statistically gated path to enforcement, evaluated under
repeated pre-registered blind protocols." Avoid "the first system to check whether review
comments were addressed": that claim is false.

## Sources

- Sun et al., Does AI Code Review Lead to Code Changes? A Case Study of GitHub Actions (arXiv 2508.18771): https://arxiv.org/html/2508.18771v1
- GitHub Changelog, Auto-resolution and analysis updates in Copilot code review (2026-09-11): https://github.blog/changelog/2026-09-11-auto-resolution-and-analysis-updates-in-copilot-code-review/
- CodeRabbit docs, request-changes workflow: https://docs.coderabbit.ai/pr-reviews/request-changes-workflow
- Google Research, Resolving code review comments with ML (2023): https://research.google/blog/resolving-code-review-comments-with-ml/
- Tufano et al., Towards Automating Code Review Activities (ICSE 2021): https://arxiv.org/abs/2101.02518
- Li et al., CodeReviewer / Automating Code Review Activities by Large-Scale Pre-training (ESEC/FSE 2022): https://arxiv.org/abs/2203.09095
- Bosu, Greiler, Bird, Characteristics of Useful Code Reviews (MSR 2015): https://www.microsoft.com/en-us/research/?p=168510
- Rahman, Roy, Kula, Predicting Usefulness of Code Review Comments (MSR 2017): https://arxiv.org/abs/1807.04485
- Beller et al., Modern Code Reviews in Open-Source Projects: Which Problems Do They Fix? (MSR 2014): https://flosshub.org/node/1650
- Panthaplackel et al., Deep Just-In-Time Inconsistency Detection Between Comments and Source Code (AAAI 2021): https://arxiv.org/abs/2010.01625
- Falleri et al., Fine-grained and accurate source code differencing (GumTree, ASE 2014): https://github.com/gumtreediff/gumtree
- Falleri and Martinez, Fine-grained, accurate and scalable source differencing (ICSE 2024): https://conf.researchr.org/details/icse-2024/icse-2024-research-track/148/Fine-grained-accurate-and-scalable-source-differencing
- RovoDev Code Reviewer at Atlassian (arXiv 2601.01129): https://arxiv.org/html/2601.01129v2
- CRScore (arXiv 2409.19801): https://arxiv.org/pdf/2409.19801 · HalluJudge (arXiv 2601.19072): https://arxiv.org/pdf/2601.19072 · CRJudgeBench (arXiv 2609.37216): https://arxiv.org/html/2609.37216v1
- Prompt injection via GitHub comments (SecurityWeek, 2026): https://www.securityweek.com/claude-code-gemini-cli-github-copilot-agents-vulnerable-to-prompt-injection-via-comments/amp/ · Cloudflare on AI code review prompt injection: https://itbrief.com.au/story/cloudflare-warns-of-ai-code-review-prompt-injection
- MSR registered reports track: https://2026.msrconf.org/track/msr-2026-registered-reports
