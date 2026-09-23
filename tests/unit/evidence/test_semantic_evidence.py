from pathlib import Path

import pytest

from helpers.cases import make_case
from helpers.semantic import fake_encoder
from verireview.contracts import (
    EvidenceSource,
    Requirement,
    RequirementCategory,
    ReviewCase,
    ReviewRequirement,
)
from verireview.dataset import iter_fixtures
from verireview.evidence.semantic import KIND, SemanticRelevanceStage, requirement_relevance
from verireview.ingestion import make_unified_diff
from verireview.verification import SEMANTIC_VERSION, mvp_pipeline, semantic_pipeline

DATASET = Path(__file__).resolve().parents[3] / "dataset"
BEFORE = "def save(db, username):\n    db.insert(username)\n"
AFTER = (
    "def save(db, username):\n"
    "    if username is None:\n"
    "        raise ValueError('username required')\n"
    "    db.insert(username)\n"
    "    audit.log(db)\n"
)
REQUIREMENTS = ReviewRequirement(
    case_id="c",
    target_file="m.py",
    requirements=[
        Requirement(id="R1", category=RequirementCategory.VALIDATION, description="username None"),
        Requirement(id="R2", category=RequirementCategory.OTHER, description="audit log"),
    ],
    source="manual",
)


def case(after: str = AFTER) -> ReviewCase:
    diff = make_unified_diff(BEFORE, after, "m.py", "m.py")
    return make_case(BEFORE, after, 2).model_copy(update={"unified_diff": diff})


def test_each_requirement_cites_its_best_matching_added_code() -> None:
    items = SemanticRelevanceStage(fake_encoder)(case(), REQUIREMENTS)

    assert [(e.requirement_id, e.location.line_start if e.location else 0) for e in items] == [
        ("R1", 2),
        ("R2", 5),
    ]
    assert all(e.kind == KIND and e.source == EvidenceSource.SEMANTIC for e in items)
    assert "best of 2 added chunk(s)" in items[0].detail


def test_semantic_evidence_is_neutral() -> None:
    """It informs; it never supports or contradicts on its own (Phase 8b decides)."""
    items = SemanticRelevanceStage(fake_encoder)(case(), REQUIREMENTS)

    assert {e.passed for e in items} == {None}
    assert "does not affect the verdict" in items[0].detail


def test_comment_only_change_gives_no_semantic_evidence() -> None:
    after = BEFORE.replace("    db.insert", "    # username None audit log\n    db.insert")

    assert SemanticRelevanceStage(fake_encoder)(case(after), REQUIREMENTS) == []


def test_relevance_ignores_comments_that_repeat_the_request() -> None:
    """The Phase 6 trap: a comment echoing the reviewer must not raise relevance."""
    commented = AFTER.replace(
        "    db.insert", "    # username None: validated, audit log done\n    db.insert"
    )

    plain = requirement_relevance(case(), REQUIREMENTS, fake_encoder)
    echoed = requirement_relevance(case(commented), REQUIREMENTS, fake_encoder)

    assert [r.score for r in echoed] == pytest.approx([r.score for r in plain])


@pytest.mark.parametrize("root", ["fixtures", "heldout_fixtures"])
def test_semantic_pipeline_never_changes_a_verdict(root: str) -> None:
    rules, semantic = mvp_pipeline(), semantic_pipeline(fake_encoder)

    for fixture in iter_fixtures(DATASET / root):
        expected, actual = rules.run(fixture.case), semantic.run(fixture.case)

        assert (actual.verdict, actual.confidence) == (expected.verdict, expected.confidence)
        assert [s.status for s in actual.per_requirement] == [
            s.status for s in expected.per_requirement
        ]
        assert actual.pipeline_version == SEMANTIC_VERSION


def test_semantic_evidence_appears_in_the_explanation() -> None:
    fixture = next(iter_fixtures(DATASET / "fixtures"))
    result = semantic_pipeline(fake_encoder).run(fixture.case)

    semantic = [e for e in result.evidence if e.kind == KIND]
    assert semantic
    assert f"• [{semantic[0].id}] Code-model relevance" in result.explanation
