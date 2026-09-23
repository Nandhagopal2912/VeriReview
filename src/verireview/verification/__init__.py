"""Evidence aggregation into a verification verdict (Phase 8)."""

from verireview.evidence.locality import change_locality_evidence
from verireview.requirements.stub import whole_comment_requirement
from verireview.verification.pipeline import Decision, Pipeline
from verireview.verification.preliminary import locality_aggregator

PRELIMINARY_VERSION = "phase2-locality-1"


def preliminary_pipeline() -> Pipeline:
    """Phase 2 baseline: stub requirement + change locality + naive aggregation."""
    return Pipeline(
        version=PRELIMINARY_VERSION,
        requirement_stage=whole_comment_requirement,
        evidence_stages=[change_locality_evidence],
        aggregator=locality_aggregator,
    )


__all__ = ["PRELIMINARY_VERSION", "Decision", "Pipeline", "preliminary_pipeline"]
