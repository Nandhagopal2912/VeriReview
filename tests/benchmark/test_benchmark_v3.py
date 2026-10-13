"""Benchmark v3 (Phase 10.2), frozen on 2026-10-13 BEFORE any rule change, so the rule work that
follows cannot be fitted to it.

- The controlled and adversarial test sets were written blind (no verifier ran on them).
- The real-world cases come from pull requests used by no earlier version and were labelled by
  one human annotator before any verifier ran on them.
- From the freeze on, the v2 test split is dev data.
"""

import hashlib
from pathlib import Path

import pytest

from verireview import cli
from verireview.benchmark import Split, iter_benchmark, iter_real_world
from verireview.benchmark.manifest import Manifest, verify
from verireview.benchmark.store import CURRENT_VERSION, get_version
from verireview.contracts import RequirementCategory, Verdict
from verireview.dataset import Fixture, iter_fixtures
from verireview.dataset.fixtures import HardCase
from verireview.evaluation import dataset_hash

DATASET = Path(__file__).resolve().parents[2] / "dataset"
V2 = DATASET / "benchmark" / "v2"
V3 = DATASET / "benchmark" / "v3"
FROZEN_V3 = {
    "controlled": "3fc99b745a361d9cbe7c1a7c7cdc5744cf14fe4608615c27d96ef6b30069ae89",
    "adversarial": "fdef0943fc66d129b6ac6cdd484782b59abb79a3e592982c92c20976c87684d0",
}
# The 60 real-world test cases with their gold labels (one human annotator), frozen in
# benchmark/v3/manifest.json before any rule change of the phase that follows.
REAL_WORLD_V3_SHA256 = "42a5a98edbf11ca474e2067efe09d3a771979452ebaf4c21c5959931e0048d59"
# The cases alone (case.json + provenance.json, no labels).
REAL_WORLD_V3_CASES_SHA256 = "84b1c8e1a7d5a2b51c80af7b97321ccd35de03a3389fe918580148e703b59e45"
CASES = [f for name in FROZEN_V3 for f in iter_fixtures(V3 / name)]


@pytest.mark.parametrize("name", sorted(FROZEN_V3))
def test_v3_authored_test_sets_are_frozen(name: str) -> None:
    assert dataset_hash(V3 / name) == FROZEN_V3[name]


def test_frozen_v3_manifest_still_matches_the_dataset() -> None:
    manifest = Manifest.model_validate_json((V3 / "manifest.json").read_text(encoding="utf-8"))

    assert manifest.version == "v3"
    assert manifest.test_sets == FROZEN_V3
    assert len(manifest.real_world_test) == 60
    assert manifest.real_world_test_hash == REAL_WORLD_V3_SHA256
    assert verify(DATASET, manifest) == []


def test_v3_real_world_cases_are_pinned_apart_from_their_labels() -> None:
    manifest = Manifest.model_validate_json((V3 / "manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    for case_id in sorted(manifest.real_world_test):
        for name in ("case.json", "provenance.json"):
            digest.update(f"{case_id}/{name}\0".encode())
            content = (V3 / "real_world" / case_id / name).read_bytes()
            digest.update(content.replace(b"\r\n", b"\n"))

    assert digest.hexdigest() == REAL_WORLD_V3_CASES_SHA256


def test_v3_real_world_gold_is_human_from_one_annotator() -> None:
    golds = [rw.gold for rw in iter_real_world(V3 / "real_world")]

    assert len(golds) == 60 and all(g is not None for g in golds)
    assert {g.label_source for g in golds if g} == {"human"}
    assert {len(g.annotators) for g in golds if g} == {1}  # not adjudicated: say so in reports
    assert sum(g.label.include for g in golds if g) == 58


def test_v3_recipe_matches_v1_and_v2() -> None:
    controlled = list(iter_fixtures(V3 / "controlled"))
    adversarial = list(iter_fixtures(V3 / "adversarial"))
    assert len(controlled) == 60 and len(adversarial) == 30
    for category in set(RequirementCategory) - {RequirementCategory.OTHER}:
        assert sum(f.meta.category == category for f in controlled) == 12
        assert sum(f.meta.category == category for f in adversarial) == 6
    assert {f.meta.expected_verdict for f in controlled} == set(Verdict)


def test_v3_has_the_same_verdict_and_difficulty_mix_as_v2() -> None:
    def mix(root: Path) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
        fixtures = list(iter_fixtures(root))
        verdicts = sorted({f.meta.expected_verdict for f in fixtures})
        hard: list[HardCase | None] = [f.meta.hard_case for f in fixtures]
        kinds = sorted({h.value if h else "" for h in hard})
        return (
            [(v.value, sum(f.meta.expected_verdict == v for f in fixtures)) for v in verdicts],
            [(k, sum((h.value if h else "") == k for h in hard)) for k in kinds],
        )

    for name in FROZEN_V3:
        assert mix(V3 / name) == mix(V2 / name)


def test_v3_is_current_and_the_v2_test_split_is_dev_data() -> None:
    assert CURRENT_VERSION == "v3"
    dev_sets = {c.case_set for c in iter_benchmark(DATASET, Split.DEV, "v3")}
    test_sets = {c.case_set for c in iter_benchmark(DATASET, Split.TEST, "v3")}

    assert {"v2-controlled", "v2-adversarial", "v2-real-world"} <= dev_sets
    assert test_sets == {"controlled", "adversarial", "real-world"}
    assert get_version("v3").real_world == "benchmark/v3/real_world"


def test_a_version_without_a_manifest_cannot_be_evaluated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The guard that kept v2 locked while v3 was being built: no manifest, no evaluation."""
    code = cli.main(["eval-benchmark", "--split", "dev", "--no-models", "--dataset", str(tmp_path)])

    assert code == 2
    assert "not frozen" in capsys.readouterr().err


def test_the_v3_test_split_needs_the_final_run_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["eval-benchmark", "--split", "test", "--no-models"]) == 2
    assert "--final-test-run" in capsys.readouterr().err


def test_v3_real_world_cases_come_from_pull_requests_unused_before() -> None:
    def pulls(directory: Path) -> dict[str, int]:
        counts: dict[str, int] = {}
        if directory.is_dir():
            for d in directory.iterdir():
                if d.is_dir():
                    pull = d.name.rsplit("__", 1)[0]
                    counts[pull] = counts.get(pull, 0) + 1
        return counts

    earlier = set(pulls(DATASET / "benchmark" / "real_world")) | set(pulls(V2 / "real_world"))
    v3 = pulls(V3 / "real_world")

    assert sum(v3.values()) == 60
    assert not set(v3) & earlier
    assert max(v3.values()) <= 3  # at most 3 threads from one pull request (FREEZE_LOG entry 2)


def test_case_ids_are_unique_across_all_versions() -> None:
    ids = [c.fixture.meta.case_id for c in iter_benchmark(DATASET, version="v3")]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("fixture", CASES, ids=lambda f: f.meta.case_id)
def test_v3_case_is_well_formed(fixture: Fixture) -> None:
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
