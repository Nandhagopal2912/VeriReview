"""Benchmark v2 (Phase 10.1). Its controlled and adversarial test sets were written and pinned
here BEFORE any rule change of Phase 10.1, so the rule work cannot be fitted to them."""

import hashlib
from pathlib import Path

import pytest

from verireview.benchmark import Split, iter_benchmark, iter_real_world
from verireview.benchmark.manifest import Manifest, verify
from verireview.contracts import RequirementCategory, Verdict
from verireview.dataset import Fixture, iter_fixtures
from verireview.evaluation import dataset_hash

DATASET = Path(__file__).resolve().parents[2] / "dataset"
V2 = DATASET / "benchmark" / "v2"
FROZEN_V2 = {
    "controlled": "8821103d65b07ce33770ce82c08e406f1d0f147c773ded0fc21a7df23a65cc84",
    "adversarial": "54f269dba37ac97d415bad8017bdee27c5fa91121c8adfa528b5daec95da5471",
}
CASES = [f for name in FROZEN_V2 for f in iter_fixtures(V2 / name)]
# Real-world v2 test cases: fresh PRs (none used in v1), frozen in benchmark/v2/manifest.json
# before any rule change of Phase 10.1. The hash covers the cases and their gold labels.
# 2026-10-11 (FREEZE_LOG entry 6): the provisional Claude labels were replaced by one human
# annotator's labels; only the gold.json files changed. Until then the hash was
# 34133f451723607e597faa8b89f128a89d95219006bf5275eac344872f846dd6.
# 2026-10-14 (FREEZE_LOG entry 7): a second annotator labelled 36 of the cases and the 19
# disagreements were adjudicated; again only gold.json files changed. Until then the hash was
# 7c2627763b2d5e3c6f5eae0823e016fbf3450e47867a0e07e4a752ee9332c3b1.
REAL_WORLD_V2_SHA256 = "9f57d62d6cac10412f1083236bdcc8b1598352d333126736789fce1f46f47998"
# The cases themselves (case.json + provenance.json, no labels): unchanged since the freeze.
REAL_WORLD_V2_CASES_SHA256 = "9dd0d8bd2f25589743501fcc9274040c8cbe0fa9721bb0295d4b32bd4660bc87"


@pytest.mark.parametrize("name", sorted(FROZEN_V2))
def test_v2_test_sets_are_frozen(name: str) -> None:
    assert dataset_hash(V2 / name) == FROZEN_V2[name]


def test_frozen_v2_manifest_still_matches_the_dataset() -> None:
    manifest = Manifest.model_validate_json((V2 / "manifest.json").read_text(encoding="utf-8"))

    assert manifest.version == "v2"
    assert manifest.test_sets == FROZEN_V2
    assert len(manifest.real_world_test) == 60
    assert manifest.real_world_test_hash == REAL_WORLD_V2_SHA256
    assert verify(DATASET, manifest) == []


def test_v2_real_world_cases_are_unchanged_by_the_relabelling() -> None:
    manifest = Manifest.model_validate_json((V2 / "manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    for case_id in sorted(manifest.real_world_test):
        for name in ("case.json", "provenance.json"):
            digest.update(f"{case_id}/{name}\0".encode())
            content = (V2 / "real_world" / case_id / name).read_bytes()
            digest.update(content.replace(b"\r\n", b"\n"))

    assert digest.hexdigest() == REAL_WORLD_V2_CASES_SHA256


def test_v2_real_world_gold_is_human_two_annotators_for_36() -> None:
    golds = [g for rw in iter_real_world(V2 / "real_world") if (g := rw.gold) is not None]

    assert len(golds) == 60
    assert {g.label_source for g in golds} == {"human"}
    two = [g for g in golds if len(g.annotators) == 2]
    assert len(two) == 36  # 17 agreed + 19 adjudicated; the other 24: one annotator, say so
    assert sum(not g.agreed for g in two) == 19
    assert all(g.adjudication_reason for g in two if not g.agreed)


def test_v2_real_world_cases_come_from_pull_requests_unused_in_v1() -> None:
    def pulls(split_dir: Path) -> set[str]:
        return {d.name.rsplit("__", 1)[0] for d in split_dir.iterdir() if d.is_dir()}

    assert not pulls(V2 / "real_world") & pulls(DATASET / "benchmark" / "real_world")


def test_v2_recipe_matches_v1() -> None:
    controlled = list(iter_fixtures(V2 / "controlled"))
    adversarial = list(iter_fixtures(V2 / "adversarial"))
    assert len(controlled) == 60 and len(adversarial) == 30
    for category in set(RequirementCategory) - {RequirementCategory.OTHER}:
        assert sum(f.meta.category == category for f in controlled) == 12
        assert sum(f.meta.category == category for f in adversarial) == 6
    assert {f.meta.expected_verdict for f in controlled} == set(Verdict)


def test_v1_test_split_is_dev_data_in_v2() -> None:
    dev_sets = {c.case_set for c in iter_benchmark(DATASET, Split.DEV, "v2")}
    test_sets = {c.case_set for c in iter_benchmark(DATASET, Split.TEST, "v2")}

    assert {"v1-controlled", "v1-adversarial", "v1-real-world"} <= dev_sets
    assert "v1-controlled" not in test_sets and "v1-real-world" not in test_sets


def test_case_ids_are_unique_across_all_versions() -> None:
    ids = [c.fixture.meta.case_id for c in iter_benchmark(DATASET, version="v2")]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("fixture", CASES, ids=lambda f: f.meta.case_id)
def test_v2_case_is_well_formed(fixture: Fixture) -> None:
    for code in (
        fixture.case.before_code,
        fixture.case.after_code,
        *fixture.case.test_files.values(),
    ):
        assert code is not None
        compile(code, fixture.meta.case_id, "exec")
    if fixture.meta.expected_verdict == Verdict.PARTIALLY_SATISFIED:
        assert len(fixture.meta.requirements) >= 2
    assert fixture.meta.requirements[0].category == fixture.meta.category
