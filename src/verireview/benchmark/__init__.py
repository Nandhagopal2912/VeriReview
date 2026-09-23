"""Phase 9 benchmark: case sets and splits, real-world mining, annotation, agreement, gold.

See docs/phase9_benchmark.md and docs/annotation_guide.md.
"""

from verireview.benchmark.agreement import (
    AdjudicationFile,
    AgreementReport,
    PendingAdjudicationError,
    agreement,
    build_gold,
    cohen_kappa,
)
from verireview.benchmark.labels import (
    AnnotationFile,
    CaseAnnotation,
    ExclusionReason,
    RequirementLabel,
    Status,
    derive_verdict,
)
from verireview.benchmark.store import (
    CASE_SETS,
    BenchmarkCase,
    GoldLabel,
    Provenance,
    Source,
    Split,
    iter_benchmark,
    iter_real_world,
    real_world_fixture,
)

# Ten dev fixtures for the annotators' calibration round (none is a worked example in the guide).
CALIBRATION_CASES = (
    "api-001-missing-username-400",
    "api-004-todo-comment",
    "errors-002-swallowed-exception",
    "errors-003-one-of-two-exceptions",
    "errors-005-question-only",
    "naming-001-rename-parameter",
    "naming-003-comment-mentions-name",
    "testing-001-empty-username-test",
    "testing-004-one-of-two-cases",
    "validation-006-wrong-variable",
)

__all__ = [
    "CALIBRATION_CASES",
    "CASE_SETS",
    "AdjudicationFile",
    "AgreementReport",
    "AnnotationFile",
    "BenchmarkCase",
    "CaseAnnotation",
    "ExclusionReason",
    "GoldLabel",
    "PendingAdjudicationError",
    "Provenance",
    "RequirementLabel",
    "Source",
    "Split",
    "Status",
    "agreement",
    "build_gold",
    "cohen_kappa",
    "derive_verdict",
    "iter_benchmark",
    "iter_real_world",
    "real_world_fixture",
]
