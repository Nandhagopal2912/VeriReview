"""Scoring requirement extraction against gold annotations (roadmap Phase 4 targets).

Metrics:
- count_exact: fraction of comments where the number of extracted requirements equals gold
  (a non-actionable comment counts as 0 requirements).
- category precision/recall/F1: multiset overlap of categories per comment, micro-averaged.
  Order-free, so it does not depend on how requirements are aligned.
- actionable_accuracy: requests vs. comments that ask for nothing.
- ambiguity: predicted ambiguous (score ≥ threshold, or not actionable) vs. gold.
- target_symbol_accuracy: enclosing function found (fixtures only; they have a gold symbol).
"""

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from verireview.contracts import RequirementCategory, ReviewRequirement, Verdict
from verireview.dataset import Fixture
from verireview.requirements import AMBIGUITY_THRESHOLD, CodeContext, extract_requirements


@dataclass(frozen=True)
class RequirementExample:
    id: str
    comment: str
    code: str | None
    anchor_line: int | None
    gold_categories: tuple[RequirementCategory, ...]  # () = the comment asks for nothing
    gold_ambiguous: bool | None  # None = not applicable (nothing requested)
    gold_target_symbol: str | None = None


class ExampleOutcome(BaseModel):
    id: str
    gold_count: int
    predicted_count: int
    gold_categories: list[str]
    predicted_categories: list[str]
    gold_ambiguous: bool | None
    predicted_ambiguity: float | None
    predicted_ambiguous: bool
    target_symbol_ok: bool | None


class ExtractionReport(BaseModel):
    name: str
    dataset_hash: str
    n: int
    count_exact: float
    category_precision: float
    category_recall: float
    category_f1: float
    actionable_accuracy: float
    ambiguity_precision: float | None
    ambiguity_recall: float | None
    target_symbol_accuracy: float | None
    examples: list[ExampleOutcome]


def fixture_examples(fixtures: Sequence[Fixture]) -> list[RequirementExample]:
    """Dev fixtures: gold requirements from meta.json; UNCERTAIN verdict = ambiguous request."""
    return [
        RequirementExample(
            id=f.meta.case_id,
            comment=f.case.thread.root.body,
            code=f.case.before_code,
            anchor_line=f.case.anchor_line,
            gold_categories=tuple(r.category for r in f.meta.requirements),
            gold_ambiguous=f.meta.expected_verdict == Verdict.UNCERTAIN,
            gold_target_symbol=f.meta.target_symbol,
        )
        for f in fixtures
    ]


def heldout_examples(path: Path) -> list[RequirementExample]:
    examples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        examples.append(
            RequirementExample(
                id=item["id"],
                comment=item["comment"],
                code=item.get("code") or None,
                anchor_line=None,
                gold_categories=tuple(
                    RequirementCategory(r["category"]) for r in item["requirements"]
                ),
                gold_ambiguous=item["ambiguous"],
            )
        )
    return examples


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def evaluate_extraction(
    examples: Sequence[RequirementExample], name: str, dataset_hash: str
) -> ExtractionReport:
    outcomes = [_score(example, _extract(example)) for example in examples]
    matched = gold_total = predicted_total = 0
    for o in outcomes:
        gold, predicted = Counter(o.gold_categories), Counter(o.predicted_categories)
        matched += sum((gold & predicted).values())
        gold_total += sum(gold.values())
        predicted_total += sum(predicted.values())
    precision = matched / predicted_total if predicted_total else 0.0
    recall = matched / gold_total if gold_total else 0.0

    judged = [o for o in outcomes if o.gold_ambiguous is not None]
    tp = sum(bool(o.gold_ambiguous) and o.predicted_ambiguous for o in judged)
    predicted_pos = sum(o.predicted_ambiguous for o in judged)
    gold_pos = sum(bool(o.gold_ambiguous) for o in judged)
    targets = [o.target_symbol_ok for o in outcomes if o.target_symbol_ok is not None]
    n = len(outcomes)
    return ExtractionReport(
        name=name,
        dataset_hash=dataset_hash,
        n=n,
        count_exact=sum(o.gold_count == o.predicted_count for o in outcomes) / n if n else 0.0,
        category_precision=precision,
        category_recall=recall,
        category_f1=2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        actionable_accuracy=(
            sum((o.gold_count > 0) == (o.predicted_count > 0) for o in outcomes) / n if n else 0.0
        ),
        ambiguity_precision=tp / predicted_pos if predicted_pos else None,
        ambiguity_recall=tp / gold_pos if gold_pos else None,
        target_symbol_accuracy=sum(targets) / len(targets) if targets else None,
        examples=outcomes,
    )


def _extract(example: RequirementExample) -> ReviewRequirement:
    return extract_requirements(
        example.comment,
        case_id=example.id,
        context=CodeContext.from_code(example.code, example.anchor_line),
    )


def _score(example: RequirementExample, extracted: ReviewRequirement) -> ExampleOutcome:
    predicted = [r.category.value for r in extracted.requirements] if extracted.actionable else []
    ambiguous = not extracted.actionable or (extracted.ambiguity or 0.0) >= AMBIGUITY_THRESHOLD
    return ExampleOutcome(
        id=example.id,
        gold_count=len(example.gold_categories),
        predicted_count=len(predicted),
        gold_categories=[c.value for c in example.gold_categories],
        predicted_categories=predicted,
        gold_ambiguous=example.gold_ambiguous,
        predicted_ambiguity=extracted.ambiguity,
        predicted_ambiguous=ambiguous,
        target_symbol_ok=(
            extracted.target_symbol == example.gold_target_symbol
            if example.gold_target_symbol is not None
            else None
        ),
    )
