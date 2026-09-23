# VeriReview benchmark

Cases for evaluating whether code changes made after a review comment satisfy it. Labels follow
[docs/annotation_guide.md](../../docs/annotation_guide.md); build process in
[docs/phase9_benchmark.md](../../docs/phase9_benchmark.md).

| Folder | Content | Split |
|---|---|---|
| `controlled/` | 60 hand-written cases, 12 per category | test (frozen) |
| `adversarial/` | 40 hand-written traps and unusual-but-valid fixes | test (frozen) |
| `real_world/` | review threads mined from approved public repositories (`case.json`, `provenance.json`, `gold.json`) | dev / test per case |
| `LICENSES/` | license texts of the mined repositories | |

The dev split also includes `../fixtures/` (29) and `../heldout_fixtures/` (24).

**Test-split rule:** test cases are frozen by hash and are only run by the final evaluation
(Phase 10). Never edit them to make a verifier pass.

**Real-world cases** are code and review discussion from public repositories under permissive
licenses (MIT, BSD, Apache-2.0, ISC, PSF-2.0). Each case records its source URL and SPDX license id,
and the license text is in `LICENSES/`. GitHub logins are replaced by roles (`reviewer`, `author`,
`participant-N`) and e-mail addresses are masked. That is pseudonymisation, not anonymisation. The
content stays © its original authors under the repository's license.
