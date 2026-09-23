"""Structured review-requirement extraction (Phase 4)."""

from verireview.requirements.extraction import (
    CodeContext,
    ambiguity,
    categorize,
    classify_sentence,
    extract_requirements,
    extraction_stage,
)
from verireview.requirements.lexicon import AMBIGUITY_THRESHOLD
from verireview.requirements.stub import whole_comment_requirement

__all__ = [
    "AMBIGUITY_THRESHOLD",
    "CodeContext",
    "ambiguity",
    "categorize",
    "classify_sentence",
    "extract_requirements",
    "extraction_stage",
    "whole_comment_requirement",
]
