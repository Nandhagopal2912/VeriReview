# Benchmark v3 freeze log (Phase 10.2)

Order of events, recorded as they happen. **v3 is not frozen yet**: until `manifest.json` exists
in this directory, v2 remains the locked test split and no rule may change.

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

Still to do, in this order: the human labels (`build-gold`); `controlled` (60) and `adversarial`
(30) written blind from the v1/v2 recipe; `benchmark-freeze --benchmark-version v3`. Only then:
rule changes on dev data (v2 included), and one blind v3 run.
