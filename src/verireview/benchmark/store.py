"""Benchmark layout: which case sets exist, their source and split, and real-world storage.

    dataset/fixtures/                     controlled   dev   (Phase 2)
    dataset/heldout_fixtures/             controlled   dev   (Phase 5; no longer blind)
    dataset/benchmark/controlled/         controlled   test  (Phase 9, frozen)
    dataset/benchmark/adversarial/        adversarial  test  (Phase 9, frozen)
    dataset/benchmark/real_world/<id>/    real_world   dev or test, per case:
        case.json         ReviewCase from ingestion, pseudonymised
        provenance.json   where it came from, license, split
        gold.json         adjudicated label (after annotation)
    dataset/benchmark/LICENSES/           license texts of the mined repositories
    dataset/annotations/<annotator>/      raw exports of the annotation page (never edited)

A real-world case takes part in evaluation only once it has gold and is included.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from verireview.benchmark.labels import CaseAnnotation
from verireview.contracts import Requirement as GoldRequirement
from verireview.contracts import ReviewCase, ReviewRequirement
from verireview.dataset import Fixture, FixtureMeta, HardCase, iter_fixtures


class Source(StrEnum):
    CONTROLLED = "controlled"
    ADVERSARIAL = "adversarial"
    REAL_WORLD = "real_world"


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


@dataclass(frozen=True)
class CaseSet:
    name: str
    path: str  # relative to the dataset root
    source: Source
    split: Split | None  # None: decided per case (real-world)


CASE_SETS = (
    CaseSet("dev-fixtures", "fixtures", Source.CONTROLLED, Split.DEV),
    CaseSet("dev-heldout", "heldout_fixtures", Source.CONTROLLED, Split.DEV),
    CaseSet("controlled", "benchmark/controlled", Source.CONTROLLED, Split.TEST),
    CaseSet("adversarial", "benchmark/adversarial", Source.ADVERSARIAL, Split.TEST),
    CaseSet("real-world", "benchmark/real_world", Source.REAL_WORLD, None),
)
REAL_WORLD = "benchmark/real_world"
LICENSES = "benchmark/LICENSES"
ANNOTATIONS = "annotations"


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    pull_number: int
    root_comment_id: int
    url: str
    license_spdx: str
    mined_at: datetime
    split: Split
    pseudonymised: bool = True
    collector_version: str


class GoldLabel(BaseModel):
    """The adjudicated label of one real-world case."""

    model_config = ConfigDict(extra="forbid")

    label: CaseAnnotation
    annotators: list[str] = Field(min_length=1)
    agreed: bool = Field(description="True: both annotators agreed; False: adjudicated.")
    adjudicator: str | None = None
    adjudication_reason: str | None = None


@dataclass(frozen=True)
class RealWorldCase:
    directory: Path
    case: ReviewCase
    provenance: Provenance
    gold: GoldLabel | None

    @property
    def case_id(self) -> str:
        return self.directory.name


@dataclass(frozen=True)
class BenchmarkCase:
    fixture: Fixture
    source: Source
    split: Split
    case_set: str


def case_dir_name(repository: str, pull_number: int, comment_id: int) -> str:
    owner, name = repository.split("/", 1)
    return f"{owner}__{name}__{pull_number}__{comment_id}"


def write_real_world(root: Path, case: ReviewCase, provenance: Provenance) -> Path:
    directory = root / case_dir_name(
        provenance.repository, provenance.pull_number, provenance.root_comment_id
    )
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory / "case.json", case.model_dump_json(indent=2))
    _write(directory / "provenance.json", provenance.model_dump_json(indent=2))
    return directory


def write_gold(directory: Path, gold: GoldLabel) -> None:
    _write(directory / "gold.json", gold.model_dump_json(indent=2, exclude_none=True))


def iter_real_world(root: Path) -> Iterator[RealWorldCase]:
    for directory in sorted(p.parent for p in root.glob("*/provenance.json")):
        gold_path = directory / "gold.json"
        yield RealWorldCase(
            directory=directory,
            case=ReviewCase.model_validate_json(_read(directory / "case.json")),
            provenance=Provenance.model_validate_json(_read(directory / "provenance.json")),
            gold=GoldLabel.model_validate_json(_read(gold_path)) if gold_path.is_file() else None,
        )


def iter_benchmark(dataset_root: Path, split: Split | None = None) -> Iterator[BenchmarkCase]:
    """Every labelled, included case, optionally of one split."""
    for case_set in CASE_SETS:
        root = dataset_root / case_set.path
        if not root.is_dir():
            continue
        if case_set.source != Source.REAL_WORLD:
            assert case_set.split is not None  # noqa: S101 - static table above
            if split in (None, case_set.split):
                for fixture in iter_fixtures(root):
                    yield BenchmarkCase(fixture, case_set.source, case_set.split, case_set.name)
            continue
        for rw in iter_real_world(root):
            if rw.gold is None or not rw.gold.label.include:
                continue
            if split in (None, rw.provenance.split):
                fixture = real_world_fixture(rw)
                yield BenchmarkCase(fixture, Source.REAL_WORLD, rw.provenance.split, case_set.name)


def real_world_fixture(rw: RealWorldCase) -> Fixture:
    """A gold-labelled real-world case in the same shape as a hand-written fixture, so the
    common ``evaluate()`` scores it unchanged."""
    if rw.gold is None or not rw.gold.label.include or rw.gold.label.verdict is None:
        raise ValueError(f"{rw.case_id}: no included gold label")
    label = rw.gold.label
    assert label.category is not None  # noqa: S101 - included labels have requirements
    requirements = [
        GoldRequirement(id=f"R{i}", category=r.category, description=r.description)
        for i, r in enumerate(label.requirements, start=1)
    ]
    meta = FixtureMeta(
        case_id=rw.case_id,
        category=label.category,
        file_path=rw.case.file_path,
        comment_line=rw.case.anchor_line or rw.case.thread.original_line or 1,
        expected_verdict=label.verdict,
        hard_case=HardCase.AMBIGUOUS if label.ambiguous else None,
        rationale=_rationale(rw.gold),
        requirements=requirements,
    )
    gold_requirement = ReviewRequirement(
        case_id=rw.case.case_id,
        target_file=rw.case.file_path,
        requirements=requirements,
        ambiguity=1.0 if label.ambiguous else 0.0,
        ambiguity_reasons=["annotated as ambiguous"] if label.ambiguous else [],
        source="manual",
    )
    return Fixture(meta=meta, case=rw.case, gold_requirement=gold_requirement)


def _rationale(gold: GoldLabel) -> str:
    text = gold.adjudication_reason or gold.label.evidence or gold.label.notes
    text = text.strip() or "Annotated verdict (see gold.json)."
    return text if len(text) >= 10 else f"Annotated: {text}"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
