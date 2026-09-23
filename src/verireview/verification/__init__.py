"""Evidence aggregation into a verification verdict (Phase 8).

Pipelines are registered by name so every phase stays runnable and comparable on the same
dataset (the ablation study in plan §21 depends on this).
"""

from collections.abc import Callable

from verireview.evidence.locality import change_locality_evidence
from verireview.evidence.requirement import requirement_evidence
from verireview.evidence.rules import rule_evidence
from verireview.evidence.semantic import SemanticRelevanceStage
from verireview.evidence.structure import structural_evidence
from verireview.evidence.tests import changed_tests_evidence
from verireview.requirements import extraction_stage
from verireview.requirements.stub import whole_comment_requirement
from verireview.semantic import Encoder
from verireview.verification.ambiguity import ambiguity_gate
from verireview.verification.pipeline import Decision, Pipeline
from verireview.verification.preliminary import locality_aggregator
from verireview.verification.reliability import reliability_adjusted
from verireview.verification.rules import rule_aggregator
from verireview.verification.structural import structural_aggregator

PRELIMINARY_VERSION = "phase2-locality-1"
STRUCTURAL_VERSION = "phase3-structure-1"
REQUIREMENTS_VERSION = "phase4-requirements-1"
RULES_VERSION = "phase5-rules-1"
MVP_VERSION = "mvp-1"
SEMANTIC_VERSION = "phase7-semantic-1"


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


def requirements_pipeline() -> Pipeline:
    """Phase 4: extracted requirements + ambiguity gate over the Phase 3 structural baseline."""
    return Pipeline(
        version=REQUIREMENTS_VERSION,
        requirement_stage=extraction_stage,
        evidence_stages=[requirement_evidence, structural_evidence, changed_tests_evidence],
        aggregator=ambiguity_gate(structural_aggregator),
    )


def rules_pipeline() -> Pipeline:
    """Phase 5: extracted requirements checked by per-category rules, behind the ambiguity gate."""
    return Pipeline(
        version=RULES_VERSION,
        requirement_stage=extraction_stage,
        evidence_stages=[
            requirement_evidence,
            structural_evidence,
            changed_tests_evidence,
            rule_evidence,
        ],
        aggregator=ambiguity_gate(rule_aggregator),
    )


def mvp_pipeline() -> Pipeline:
    """Phase 8a MVP: Phase 5 rules, with confidence lowered when the case itself is unreliable."""
    rules = rules_pipeline()
    return Pipeline(
        version=MVP_VERSION,
        requirement_stage=rules.requirement_stage,
        evidence_stages=rules.evidence_stages,
        aggregator=ambiguity_gate(reliability_adjusted(rule_aggregator)),
    )


def semantic_pipeline(encoder: Encoder | None = None) -> Pipeline:
    """Phase 7: the MVP plus code-model relevance evidence (UniXcoder, needs the `nlp` group).

    The semantic evidence is neutral and the aggregator is the MVP's, so verdicts are identical
    to ``mvp`` (pinned by a test). The model loads on first use, not here. ``encoder`` replaces
    UniXcoder (tests use a fake one).
    """
    mvp = mvp_pipeline()
    return Pipeline(
        version=SEMANTIC_VERSION,
        requirement_stage=mvp.requirement_stage,
        evidence_stages=[*mvp.evidence_stages, SemanticRelevanceStage(encoder)],
        aggregator=mvp.aggregator,
    )


PIPELINES: dict[str, Callable[[], Pipeline]] = {
    "phase2-locality": preliminary_pipeline,
    "phase3-structure": structural_pipeline,
    "phase4-requirements": requirements_pipeline,
    "phase5-rules": rules_pipeline,
    "mvp": mvp_pipeline,
    "phase7-semantic": semantic_pipeline,
}
DEFAULT_PIPELINE = "mvp"


def get_pipeline(name: str = DEFAULT_PIPELINE) -> Pipeline:
    return PIPELINES[name]()


__all__ = [
    "DEFAULT_PIPELINE",
    "MVP_VERSION",
    "PIPELINES",
    "PRELIMINARY_VERSION",
    "REQUIREMENTS_VERSION",
    "RULES_VERSION",
    "SEMANTIC_VERSION",
    "STRUCTURAL_VERSION",
    "Decision",
    "Pipeline",
    "get_pipeline",
    "mvp_pipeline",
    "preliminary_pipeline",
    "requirements_pipeline",
    "rules_pipeline",
    "semantic_pipeline",
    "structural_pipeline",
]
