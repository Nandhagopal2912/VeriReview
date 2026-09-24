# VeriReview benchmark

Cases for evaluating whether code changes made after a review comment satisfy it. Labels follow
[docs/annotation_guide.md](../../docs/annotation_guide.md); build process in
[docs/phase9_benchmark.md](../../docs/phase9_benchmark.md).

| Folder | Content | Split |
|---|---|---|
| `controlled/` | 60 hand-written cases, 12 per category | test (frozen) |
| `adversarial/` | 40 hand-written traps and unusual-but-valid fixes | test (frozen) |
| `real_world/` | 57 review threads mined from 6 approved public repositories (`case.json`, `provenance.json`, `gold.json`); 50 included | 30 dev / 20 test (included) |
| `LICENSES/` | license texts of the mined repositories | |

The dev split also includes `../fixtures/` (29) and `../heldout_fixtures/` (24).

**Test-split rule:** test cases are frozen by hash and are only run by the final evaluation
(Phase 10). Never edit them to make a verifier pass.

**Real-world cases** are code and review discussion from public repositories under permissive
licenses (MIT, BSD, Apache-2.0, ISC, PSF-2.0). Each case records its source URL and SPDX license id,
and the license text is in `LICENSES/`. GitHub logins are replaced by roles (`reviewer`, `author`,
`participant-N`) and e-mail addresses are masked. That is pseudonymisation, not anonymisation. The
content stays © its original authors under the repository's license.

**Labels of the real-world cases are provisional** (`label_source: "model"` in `gold.json`). They
were written by Claude, blind (before any verifier ran on the cases), because no human annotator was
available (owner decision, 2026-09-24). Human two-annotator labels replace them when added; the raw
labels are in `../annotations/claude/rw-v1.json`. See the annotation guide §7a.

## Attribution

| Repository | License | Cases |
|---|---|---|
| [encode/httpx](https://github.com/encode/httpx) | BSD-3-Clause | 11 |
| [home-assistant/core](https://github.com/home-assistant/core) | Apache-2.0 | 9 |
| [pallets/click](https://github.com/pallets/click) | BSD-3-Clause | 2 |
| [pandas-dev/pandas](https://github.com/pandas-dev/pandas) | BSD-3-Clause | 11 |
| [pydantic/pydantic](https://github.com/pydantic/pydantic) | MIT | 11 |
| [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | MIT | 13 |

Each case's `provenance.json` links the exact review comment. Full license texts: `LICENSES/`.
