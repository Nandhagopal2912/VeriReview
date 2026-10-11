"""Benchmark v3 (Phase 10.2), while it is being built: the layout exists so that new real-world
cases can be collected and labelled, but nothing may be evaluated on it before its test split is
frozen, because its dev split holds the v2 test split."""

from pathlib import Path

import pytest

from verireview import cli
from verireview.benchmark import Split
from verireview.benchmark.store import CURRENT_VERSION, VERSIONS, get_version

DATASET = Path(__file__).resolve().parents[2] / "dataset"
V3_FROZEN = (DATASET / get_version("v3").manifest).is_file()


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
    def pulls(directory: Path) -> set[str]:
        if not directory.is_dir():
            return set()
        return {d.name.rsplit("__", 1)[0] for d in directory.iterdir() if d.is_dir()}

    earlier = pulls(DATASET / "benchmark" / "real_world") | pulls(
        DATASET / "benchmark" / "v2" / "real_world"
    )
    assert not pulls(DATASET / "benchmark" / "v3" / "real_world") & earlier
