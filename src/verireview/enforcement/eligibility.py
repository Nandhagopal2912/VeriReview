"""Which requirement categories may ever be enforced (Phase 12, owner decision 2026-09-24).

A category is eligible only if, on a **frozen test split evaluated once** (a pre-registered
`eval-benchmark --final-test-run` report), the one-sided 95% Clopper–Pearson **upper bound** of
both its false-acceptance rate and its false-blocking rate is at most 5%. With zero errors that
needs about 60 bad and 60 good resolutions in the category, so small samples can never qualify:
a clean 0/10 still has an upper bound of 26%.

- false acceptance: predicted SATISFIED among gold NOT / PARTIALLY_SATISFIED cases
- false blocking: predicted NOT_SATISFIED among gold SATISFIED cases

The category of a case is its main (first) requirement's category, as in the benchmark reports.

The result is written to ``eligibility.json`` next to this module (shipped with the package, so
the service can read it) by ``verireview enforcement-eligibility REPORT``. It is data, generated
from a recorded run; editing it by hand defeats the gate (a test pins the shipped file).
"""

import hashlib
import json
import math
from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from verireview.contracts import RequirementCategory, Verdict
from verireview.evaluation.benchmark import CaseRecord
from verireview.evaluation.systems import BenchmarkReport

DEFAULT_THRESHOLD = 0.05
DEFAULT_CONFIDENCE = 0.95
SHIPPED = "eligibility.json"
_BAD = (Verdict.NOT_SATISFIED, Verdict.PARTIALLY_SATISFIED)


# ---------------------------------------------------------------- Clopper–Pearson


def upper_bound(errors: int, n: int, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """One-sided exact (Clopper–Pearson) upper confidence bound of a binomial rate.

    The p with P(X <= errors | n, p) = 1 - confidence, i.e. I_p(errors + 1, n - errors) =
    confidence (regularised incomplete beta), found by bisection.
    """
    if n <= 0 or errors >= n:
        return 1.0
    low, high = errors / n, 1.0
    for _ in range(200):
        mid = (low + high) / 2
        if _betainc(errors + 1, n - errors, mid) < confidence:
            low = mid
        else:
            high = mid
    return high


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b) (continued fraction, Numerical Recipes §6.4)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _betacf(a: float, b: float, x: float) -> float:
    tiny, eps = 1e-300, 1e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 1000):
        m2 = 2 * m
        for aa in (
            m * (b - m) * x / ((qam + m2) * (a + m2)),
            -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2)),
        ):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < eps:
            break
    return h


# ---------------------------------------------------------------- the report


class CategoryEvidence(BaseModel):
    category: RequirementCategory
    bad_cases: int
    false_accepts: int
    far: float | None
    far_upper: float
    good_cases: int
    false_blocks: int
    fbr: float | None
    fbr_upper: float
    eligible: bool
    reason: str


class EligibilityReport(BaseModel):
    schema_version: str = "1"
    source_report: str
    source_sha256: str
    split: str
    manifest_version: str | None
    protocol_sha256: str
    system: str
    threshold: float
    confidence: float
    categories: list[CategoryEvidence]

    def eligible_categories(self) -> frozenset[RequirementCategory]:
        return frozenset(c.category for c in self.categories if c.eligible)


def compute(
    report_path: Path,
    system: str = "F",
    threshold: float = DEFAULT_THRESHOLD,
    confidence: float = DEFAULT_CONFIDENCE,
) -> EligibilityReport:
    raw = report_path.read_bytes()
    report = BenchmarkReport.model_validate_json(raw)
    result = next((s for s in report.systems if s.system == system), None)
    if result is None:
        raise ValueError(f"system {system!r} is not in {report_path}")
    frozen = (
        report.split == "test"
        and report.manifest_version is not None
        and report.protocol_sha256 != "missing"
    )
    categories = [
        _category(
            category,
            [c for c in result.cases if c.category == category.value],
            frozen,
            threshold,
            confidence,
        )
        for category in RequirementCategory
    ]
    return EligibilityReport(
        source_report=report_path.as_posix(),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        split=report.split,
        manifest_version=report.manifest_version,
        protocol_sha256=report.protocol_sha256,
        system=system,
        threshold=threshold,
        confidence=confidence,
        categories=categories,
    )


def _category(
    category: RequirementCategory,
    cases: list[CaseRecord],
    frozen: bool,
    threshold: float,
    confidence: float,
) -> CategoryEvidence:
    bad = [c for c in cases if c.expected in _BAD]
    good = [c for c in cases if c.expected == Verdict.SATISFIED]
    fa = sum(c.predicted == Verdict.SATISFIED for c in bad)
    fb = sum(c.predicted == Verdict.NOT_SATISFIED for c in good)
    far_upper, fbr_upper = (
        upper_bound(fa, len(bad), confidence),
        upper_bound(fb, len(good), confidence),
    )
    problems = []
    if not frozen:
        problems.append("the report is not a frozen, pre-registered test run")
    if far_upper > threshold:
        problems.append(f"false-acceptance upper bound {far_upper:.3f} > {threshold}")
    if fbr_upper > threshold:
        problems.append(f"false-blocking upper bound {fbr_upper:.3f} > {threshold}")
    return CategoryEvidence(
        category=category,
        bad_cases=len(bad),
        false_accepts=fa,
        far=fa / len(bad) if bad else None,
        far_upper=round(far_upper, 4),
        good_cases=len(good),
        false_blocks=fb,
        fbr=fb / len(good) if good else None,
        fbr_upper=round(fbr_upper, 4),
        eligible=not problems,
        reason="; ".join(problems) or "both upper bounds within the threshold",
    )


def write(report: EligibilityReport, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def load_shipped() -> EligibilityReport:
    """The eligibility shipped with the package (generated from the latest frozen test run)."""
    text = resources.files("verireview.enforcement").joinpath(SHIPPED).read_text(encoding="utf-8")
    return EligibilityReport.model_validate(json.loads(text))


def eligible_categories() -> frozenset[RequirementCategory]:
    """Categories enforcement may use; empty if the shipped file is missing or unreadable."""
    try:
        return load_shipped().eligible_categories()
    except (OSError, ValueError):
        return frozenset()
