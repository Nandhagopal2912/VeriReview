"""Benchmark statistics, targets, and the frozen test-split manifest (Phase 9).

``freeze`` records the hash of every test case set and of every real-world test case (case +
gold). ``tests/benchmark`` pins the manifest, so the test split cannot change silently after
Phase 8b tuning starts. The test split is touched only by the final evaluation (Phase 10).
"""

import hashlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from verireview.benchmark.store import (
    CASE_SETS,
    REAL_WORLD,
    Source,
    Split,
    iter_benchmark,
    iter_real_world,
)
from verireview.contracts import RequirementCategory, Verdict
from verireview.evaluation import dataset_hash

MANIFEST = "benchmark/manifest.json"
MVP_CATEGORIES = [c for c in RequirementCategory if c != RequirementCategory.OTHER]


class Target(BaseModel):
    name: str
    required: int
    actual: int

    @property
    def met(self) -> bool:
        return self.actual >= self.required


class RealWorldStatus(BaseModel):
    collected: int
    dev: int
    test: int
    with_gold: int
    included: int
    excluded: int


class BenchmarkStats(BaseModel):
    by_set: dict[str, int]
    by_source_split: dict[str, int]
    test_by_category: dict[str, int]
    test_by_verdict: dict[str, int]
    real_world: RealWorldStatus
    targets: list[Target]


class Manifest(BaseModel):
    version: str
    frozen_at: datetime
    test_sets: dict[str, str]
    real_world_test: list[str]
    real_world_test_hash: str


class FreezeError(ValueError):
    pass


def stats(dataset_root: Path, real_world_target: int = 50) -> BenchmarkStats:
    cases = list(iter_benchmark(dataset_root))
    test = [c for c in cases if c.split == Split.TEST]
    rw = (
        list(iter_real_world(dataset_root / REAL_WORLD))
        if (dataset_root / REAL_WORLD).is_dir()
        else []
    )
    labelled = [r for r in rw if r.gold is not None]
    by_source = Counter(c.source for c in cases)
    test_categories = Counter(c.fixture.meta.category for c in test)
    return BenchmarkStats(
        by_set=dict(Counter(c.case_set for c in cases)),
        by_source_split=dict(Counter(f"{c.source.value}/{c.split.value}" for c in cases)),
        test_by_category={k.value: test_categories[k] for k in MVP_CATEGORIES},
        test_by_verdict={
            v.value: sum(c.fixture.meta.expected_verdict == v for c in test) for v in Verdict
        },
        real_world=RealWorldStatus(
            collected=len(rw),
            dev=sum(r.provenance.split == Split.DEV for r in rw),
            test=sum(r.provenance.split == Split.TEST for r in rw),
            with_gold=len(labelled),
            included=sum(r.gold is not None and r.gold.label.include for r in rw),
            excluded=sum(r.gold is not None and not r.gold.label.include for r in rw),
        ),
        targets=[
            Target(name="controlled cases", required=100, actual=by_source[Source.CONTROLLED]),
            Target(name="adversarial cases", required=30, actual=by_source[Source.ADVERSARIAL]),
            Target(
                name="real-world cases (v1)",
                required=real_world_target,
                actual=by_source[Source.REAL_WORLD],
            ),
            *[
                Target(name=f"test cases: {k.value}", required=20, actual=test_categories[k])
                for k in MVP_CATEGORIES
            ],
            Target(
                name="verdict classes in test",
                required=len(Verdict),
                actual=len({c.fixture.meta.expected_verdict for c in test}),
            ),
        ],
    )


def real_world_test_hash(dataset_root: Path, case_ids: list[str]) -> str:
    digest = hashlib.sha256()
    for case_id in sorted(case_ids):
        directory = dataset_root / REAL_WORLD / case_id
        for name in ("case.json", "provenance.json", "gold.json"):
            digest.update(f"{case_id}/{name}\0".encode())
            digest.update((directory / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def freeze(dataset_root: Path, version: str, now: datetime | None = None) -> Manifest:
    root = dataset_root / REAL_WORLD
    rw = list(iter_real_world(root)) if root.is_dir() else []
    test_ids = [r.case_id for r in rw if r.provenance.split == Split.TEST]
    missing = [r.case_id for r in rw if r.provenance.split == Split.TEST and r.gold is None]
    if missing:
        raise FreezeError(f"real-world test cases without gold: {missing}")
    return Manifest(
        version=version,
        frozen_at=now or datetime.now(UTC),
        test_sets={
            s.name: dataset_hash(dataset_root / s.path)
            for s in CASE_SETS
            if s.split == Split.TEST and (dataset_root / s.path).is_dir()
        },
        real_world_test=sorted(test_ids),
        real_world_test_hash=real_world_test_hash(dataset_root, test_ids),
    )


def verify(dataset_root: Path, manifest: Manifest) -> list[str]:
    """Differences between the dataset and a frozen manifest ([] = unchanged)."""
    current = freeze(dataset_root, manifest.version, manifest.frozen_at)
    problems = [
        f"{name}: hash changed"
        for name, digest in manifest.test_sets.items()
        if current.test_sets.get(name) != digest
    ]
    if current.real_world_test != manifest.real_world_test:
        problems.append("real-world test case list changed")
    elif current.real_world_test_hash != manifest.real_world_test_hash:
        problems.append("real-world test cases changed")
    return problems
