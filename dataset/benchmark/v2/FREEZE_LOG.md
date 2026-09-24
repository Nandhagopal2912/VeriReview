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

Caveat: the cases were written by the same author as the rules, after the v1 error analysis. The
recipe (categories, verdict mix, difficult-case types) was kept identical to v1 to limit targeting,
but it cannot be ruled out. The fresh real-world cases are the independent part.
