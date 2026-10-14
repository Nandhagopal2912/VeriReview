# Benchmark v2 freeze log (Phase 10.1)

Order of events, recorded as they happened:

1. **2026-09-24**: v1 test split evaluated once (Phase 10); its cases became dev data for v2.
2. **2026-09-24**: v2 `controlled` (60) and `adversarial` (30) written blind, from the same recipe
   as v1, and their hashes pinned in `tests/benchmark/test_benchmark_v2.py`, **before any rule
   change of Phase 10.1**:
   - controlled `8821103d65b07ce33770ce82c08e406f1d0f147c773ded0fc21a7df23a65cc84`
   - adversarial `54f269dba37ac97d415bad8017bdee27c5fa91121c8adfa528b5daec95da5471`
3. **2026-09-24**: v2 `real_world`: 60 threads from fresh pull requests (10 per approved repo,
   seed 20260925; the 6 candidate PRs already used in v1 were skipped), all in the test split.
   Labelled blind by Claude (`dataset/annotations/claude/rw-v2.json`, provisional
   `label_source: model`) before any verifier ran on them: 57 included (50 satisfied,
   3 not satisfied, 4 uncertain; 40 of 57 are `other` requests), 3 excluded (questions).
   Frozen in `manifest.json` (`real_world_test_hash`
   `34133f451723607e597faa8b89f128a89d95219006bf5275eac344872f846dd6`) and pinned in
   `tests/benchmark/test_benchmark_v2.py`, **before any rule change of Phase 10.1**.
   Per-category test targets: validation and api_behavior have 18 of 20 (real-world requests are
   mostly `other`); recorded, not padded.
4. Rule changes are developed on dev data only (v1 test cases included).
5. v2 test evaluated once, with the Phase 10 protocol.
6. **2026-10-11**: the `real_world` labels changed, after the test was used (step 5). One human
   annotator (Jordan) labelled all 60 cases blind, from the page made by
   `annotation-sheet --batch rw-v2 --relabel-model` (the model labels are not shown), export in
   `dataset/annotations/jordan/rw-v2.json`. `build-gold … --single-source human` replaced the
   provisional Claude labels: 52 included (was 57), 8 excluded (was 3). Only the 60 `gold.json`
   files changed; the cases did not (pinned separately:
   `9dd0d8bd2f25589743501fcc9274040c8cbe0fa9721bb0295d4b32bd4660bc87`). `real_world_test_hash`
   went from `34133f45…46dd6` to
   `7c2627763b2d5e3c6f5eae0823e016fbf3450e47867a0e07e4a752ee9332c3b1`.
   - This is one annotator: not adjudicated, and no human–human agreement can be measured.
   - Claude against Jordan (`verireview agreement`): the same verdict on 43 of 49 cases both
     included (kappa 0.599); inclusion differs on 11 of 60.
   - The recorded run (`experiments/phase10_1_test.json`) was **not** run again. Its stored
     predictions were re-scored (`verireview rescore-report`,
     `experiments/phase10_2_v2_rescored_human_labels.json`). Three cases that only the human
     labels include have no stored prediction and are not scored.
   - No rule was changed for or after this relabelling. The split stays a used test split: it
     becomes dev data only once a v3 test set is frozen.
7. **2026-10-14**: a second annotator (Nandha, the project owner) labelled 36 of the cases blind,
   from `rw-v2-second.html` (sheet version 2: nothing pre-selected): the 21 where Claude and
   Jordan disagreed, plus 15 drawn at random (seed 20261011). Export:
   `dataset/annotations/nandha/annotations-Nandha-rw-v2-second.json`.
   - Agreement with Jordan (`verireview agreement`): random 15: 15 of 15 the same (14 satisfied,
     1 uncertain: easy cases). Disputed 21: 5 of 21 the same. All 36: verdict kappa 0.33 (20 of
     28 both included), 19 disagreements. Nandha excluded no case; Jordan had excluded 8 as
     `no_requirement`. Nandha had seen system results before, so this is not a fully
     independent second opinion.
   - The 19 disagreements were adjudicated by the two annotators together, each with a written
     reason: 11 Jordan's label, 4 Nandha's, 4 combined.
   - **One decision revised on re-check.** Claude pointed out a fact about the code: in
     pydantic 13611 (3747171293) the single highlighted line is absent from the new code. That
     case was "not satisfied" in the first adjudication, against the system's "satisfied". The
     annotators re-checked it and changed it to satisfied: the whole five-line comment, including
     that line, was removed. The revision was made knowing the system's verdict. The first
     export was replaced and not kept. Its reason for this case is preserved in the `gold.json`
     of commit `bca6f2a`. The export kept is
     `dataset/annotations/jordon-nandha/adjudication-jordon-nandha-rw-v2-second (1).json`; it
     differs from the first only in this decision.
   - `build-gold … --adjudication …` wrote the 36 `gold.json` files (17 agreed, 19
     adjudicated). The other 24 cases keep Jordan's single label. Included 55 (was 52):
     46 satisfied, 5 not satisfied, 4 uncertain. Again only `gold.json` files changed (the
     cases hash above still holds). `real_world_test_hash` went from `7c262776…332c3b1` to
     `9f57d62d…f47998` (first adjudication), then to
     `7fbbd8a4963f3ed7facb42910ed7666ff928b86bd1ba20e955c11a69b2cc7124` (revised).
   - The recorded run was re-scored again, not re-run
     (`experiments/phase10_2_v2_rescored_adjudicated.json`). On the 52 cases with a stored
     prediction: 23 decided, 22 right; **0 of 4** bad resolutions accepted (under Jordan's labels
     alone: 1 of 7). The pydantic 13690 docstring case, the earlier false acceptance, is now
     satisfied: the system was right.
   - No rule was changed. v2 is dev data (since the v3 freeze).

Caveat: the cases were written by the same author as the rules, after the v1 error analysis. The
recipe (categories, verdict mix, difficult-case types) was kept identical to v1 to limit targeting,
but it cannot be ruled out. The fresh real-world cases are the independent part.
