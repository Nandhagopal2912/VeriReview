"""Evidence aggregation into a verification verdict (Phase 8).

Pipelines are registered by name so every phase stays runnable and comparable on the same
dataset (the ablation study in plan §21 depends on this).
"""

from collections.abc import Callable

from verireview.evidence.locality import change_locality_evidence
from verireview.evidence.structure import structural_evidence
from verireview.evidence.tests import changed_tests_evidence
from verireview.requirements.stub import whole_comment_requirement
from verireview.verification.pipeline import Decision, Pipeline
from verireview.verification.preliminary import locality_aggregator
from verireview.verification.structural import structural_aggregator

PRELIMINARY_VERSION = "phase2-locality-1"
STRUCTURAL_VERSION = "phase3-structure-1"


def preliminary_pipeline() -> Pipeline:
    """Phase 2 baseline: stub requirement + change within a line radius + naive aggregation."""
    return Pipeline(
        version=PRELIMINARY_VERSION,
        requirement_stage=whole_comment_requirement,
        evidence_stages=[change_locality_evidence],
        aggregator=locality_aggregator,
    )


def structural_pipeline() -> Pipeline:
    """Phase 3 baseline: stub requirement + symbol-scoped structural change + test changes."""
    return Pipeline(
        version=STRUCTURAL_VERSION,
        requirement_stage=whole_comment_requirement,
        evidence_stages=[structural_evidence, changed_tests_evidence],
        aggregator=structural_aggregator,
    )


PIPELINES: dict[str, Callable[[], Pipeline]] = {
    "phase2-locality": preliminary_pipeline,
    "phase3-structure": structural_pipeline,
}
DEFAULT_PIPELINE = "phase3-structure"


def get_pipeline(name: str = DEFAULT_PIPELINE) -> Pipeline:
    return PIPELINES[name]()


__all__ = [
    "DEFAULT_PIPELINE",
    "PIPELINES",
    "PRELIMINARY_VERSION",
    "STRUCTURAL_VERSION",
    "Decision",
    "Pipeline",
    "get_pipeline",
    "preliminary_pipeline",
    "structural_pipeline",
]
