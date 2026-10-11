"""Benchmark v3 (Phase 10.2). Its controlled and adversarial test sets were written blind (no
verifier ran on them) and pinned here BEFORE any rule change, so the rule work that follows cannot
be fitted to them. The real-world cases are collected and wait for human labels; until
``v3/manifest.json`` exists nothing may be evaluated on v3, because its dev split holds the v2
test split."""

from pathlib import Path

import pytest

from verireview import cli
from verireview.benchmark import Split, iter_benchmark
from verireview.benchmark.store import CURRENT_VERSION, VERSIONS, get_version
from verireview.contracts import RequirementCategory, Verdict
from verireview.dataset import Fixture, iter_fixtures
from verireview.dataset.fixtures import HardCase
from verireview.evaluation import dataset_hash

DATASET = Path(__file__).resolve().parents[2] / "dataset"
V2 = DATASET / "benchmark" / "v2"
V3 = DATASET / "benchmark" / "v3"
V3_FROZEN = (DATASET / get_version("v3").manifest).is_file()
FROZEN_V3 = {
    "controlled": "3fc99b745a361d9cbe7c1a7c7cdc5744cf14fe4608615c27d96ef6b30069ae89",
    "adversarial": "fdef0943fc66d129b6ac6cdd484782b59abb79a3e592982c92c20976c87684d0",
}
CASES = [f for name in FROZEN_V3 for f in iter_fixtures(V3 / name)]


@pytest.mark.parametrize("name", sorted(FROZEN_V3))
def test_v3_authored_test_sets_are_frozen(name: str) -> None:
    assert dataset_hash(V3 / name) == FROZEN_V3[name]


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


def test_v2_test_split_is_dev_data_in_the_v3_layout() -> None:
    sets = {s.name: s for s in get_version("v3").case_sets}

    assert {sets[n].split for n in ("v2-controlled", "v2-adversarial", "v2-real-world")} == {
        Split.DEV
    }
    assert sets["controlled"].split == Split.TEST and sets["adversarial"].split == Split.TEST
    assert sets["controlled"].path.startswith("benchmark/v3/")
    assert get_version("v3").real_world == "benchmark/v3/real_world"


@pytest.mark.skipif(V3_FROZEN, reason="v3 is frozen: it is the current version from then on")
def test_v2_stays_current_and_v3_cannot_be_evaluated_before_its_freeze(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert CURRENT_VERSION == "v2" and "v3" in VERSIONS

    code = cli.main(
        ["eval-benchmark", "--split", "dev", "--benchmark-version", "v3", "--no-models"]
    )

    assert code == 2
    assert "not frozen" in capsys.readouterr().err


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
    ids = [f.meta.case_id for f in CASES]
    ids += [c.fixture.meta.case_id for c in iter_benchmark(DATASET, version="v2")]
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
