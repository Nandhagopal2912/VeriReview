# Benchmark v3 freeze log (Phase 10.2)

Order of events, recorded as they happen. **v3 was frozen on 2026-10-13** (entry 7), before any rule
change. From then on the v2 test split is dev data.

1. **2026-10-11**: the v2 real-world labels were replaced by one human annotator's labels and the
   recorded v2 run was re-scored without running again (`../v2/FREEZE_LOG.md`, entry 6). No rule
   changed.
2. **2026-10-11**: collection rule for the v3 `real_world` cases, written down **before** any case
   was collected:
   - candidates: resolved review threads on `.py` files by a human reviewer other than the author,
     from merged pull requests of the six approved repositories (`../repositories.json`), mined
     with `mine-candidates` (the 250 most recently updated closed pull requests of each; 800 for
     the three repositories with few unused candidates), together with the unused candidates of
     the v2 mining;
   - only pull requests used by no earlier version (enforced by `collect-cases`);
   - at most 3 threads from one pull request (`--max-per-pull 3`, new in v3: in v2 one pull
     request supplied 7 of the 60 cases);
   - seed `20261011`, every case in the test split (`--test-fraction 1.0`);
   - 10 cases per repository. A repository that cannot supply 10 gives what it has; the shortfall
     is filled from the other repositories, one extra case each in alphabetical order of the
     repository name, repeated until 60 cases or no candidates are left, and never more than 15
     from one repository;
   - the collector's own skips apply unchanged (file deleted or over 150,000 characters, thread not
     found).
3. **2026-10-11**: the v3 `real_world` cases were collected with that rule: **60 cases from 45
   pull requests**, at most 3 per pull request, all in the test split, none from a pull request
   used in v1 or v2 (`tests/benchmark/test_benchmark_v3.py`).
   - Per repository: encode/httpx 11, home-assistant/core 11, pallets/click 11,
     pandas-dev/pandas 7, pydantic/pydantic 10, pytest-dev/pytest 10. pandas could supply only 7
     (four candidates were in files over 150,000 characters, one had no usable window), so the
     first three repositories in alphabetical order gave one extra case each.
   - Mined: 301 candidate threads from the 250 most recently updated closed pull requests of each
     repository, and 326 from the 800 of click, pydantic and httpx.
   - Review comments date from 2019 to 2026 (26 of 60 from 2026). Pseudonymised; licenses
     BSD-3-Clause 29, MIT 20, Apache-2.0 11.
   - **No verifier has run on these cases, and they have no labels yet.**
4. **2026-10-11**: labelling pages for the human annotators (`dataset/raw/sheets/`, not
   committed): `rw-v3.html` (all 60), and a split for two annotators made by shuffling the sorted
   case ids with seed `20261011`: the first 20 `rw-v3-shared.html` (both annotators), the next 20
   `rw-v3-a.html`, the last 20 `rw-v3-b.html`.
5. **2026-10-11**: v3 `controlled` (60) and `adversarial` (30) written blind and pinned in
   `tests/benchmark/test_benchmark_v3.py`, **before any rule change**:
   - controlled `3fc99b745a361d9cbe7c1a7c7cdc5744cf14fe4608615c27d96ef6b30069ae89`
   - adversarial `fdef0943fc66d129b6ac6cdd484782b59abb79a3e592982c92c20976c87684d0`
   - Blind means: no verifier ran on them; they were only loaded and compiled. The rules are the
     ones of Phase 10.1 (the only code changes since are a cited line number and the advisory
     service).
   - Same recipe as v1 and v2: 12 controlled and 6 adversarial cases per category; per category
     5 satisfied, 2 partial, 3 not satisfied, 2 uncertain (controlled) and 1 satisfied, 1 partial,
     4 not satisfied (adversarial); the same counts of every difficult-case type as v2 (a test
     compares the two). New scenarios; as in v2, the adversarial cases are six resolutions of one
     request per category.

6. **2026-10-13**: the 60 `real_world` cases were labelled by one human annotator (Jordan), blind,
   on the page `rw-v3.html`; raw export `dataset/annotations/jordan/rw-v3.json` (unedited). No
   verifier had run on the cases. `build-gold … --single-source human --benchmark-version v3`:
   - 58 included, 2 excluded (no requirement);
   - verdicts: 42 satisfied, 2 partially satisfied, 5 not satisfied, 9 uncertain;
   - main request: other 32, api_behavior 11, testing 9, validation 3, error_handling 2, naming 1.
   - This is one annotator: not adjudicated, and no human–human agreement can be measured.
7. **2026-10-13**: **frozen** with `benchmark-freeze --benchmark-version v3` (`manifest.json`),
   pinned in `tests/benchmark/test_benchmark_v3.py`:
   - controlled and adversarial: the hashes of entry 5, unchanged;
   - `real_world_test_hash` (cases and labels)
     `42a5a98edbf11ca474e2067efe09d3a771979452ebaf4c21c5959931e0048d59`;
   - the cases without their labels
     `84b1c8e1a7d5a2b51c80af7b97321ccd35de03a3389fe918580148e703b59e45`.
   - The test split has **148 cases**: 60 controlled, 30 adversarial, 58 real-world (72 satisfied,
     17 partially satisfied, 40 not satisfied, 19 uncertain). Per-category targets of 20 test
     cases: naming has 19 (real-world requests are mostly `other`); recorded, not padded.
   - The dev split has 345 cases (everything of v1 and v2). `CURRENT_VERSION` is `v3`.
   - **No rule had changed, and no verifier had run on any v3 test case.**

8. **2026-10-14** (Phase 10.3): rule and extraction changes were made on dev data only (345
   cases). Then the protocol was pre-registered: `docs/phase10_3_protocol.md`, sha256
   `e3e12c93436c…`, with rules source hash `211a02c7d119…`.
9. **2026-10-14**: v3 test evaluated **once**, old rules (commit `a71e55c`) against new
   (`experiments/phase10_3_test_old_rules.json`, `experiments/phase10_3_test.json`, paired:
   `experiments/phase10_3_test_paired.json`). From now on the v3 test cases have been looked at.
   Further rule changes need a v4 test set, frozen before the changes; v3 then becomes dev data.

Caveat, as for v2: the controlled and adversarial cases were written by the same author as the
rules, who had seen the v2 results (though not an error analysis of the human-labelled v2 cases,
which waits for the freeze). The recipe was kept identical to limit targeting, but it cannot be
ruled out. The real-world cases, labelled by humans, are the independent part.
