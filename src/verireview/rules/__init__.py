"""Deterministic verification rules per requirement category (Phase 5)."""

from verireview.contracts import Requirement, RequirementCategory
from verireview.rules.api import api_rule
from verireview.rules.base import (
    Rule,
    RuleContext,
    RuleOutcome,
    RuleStatus,
)
from verireview.rules.errors import error_handling_rule
from verireview.rules.naming import naming_rule
from verireview.rules.other import other_rule, suggestion_rule
from verireview.rules.testing import testing_rule
from verireview.rules.validation import validation_rule

RULES: dict[RequirementCategory, Rule] = {
    RequirementCategory.NAMING: naming_rule,
    RequirementCategory.VALIDATION: validation_rule,
    RequirementCategory.TESTING: testing_rule,
    RequirementCategory.ERROR_HANDLING: error_handling_rule,
    RequirementCategory.API_BEHAVIOR: api_rule,
}


def check_requirement(requirement: Requirement, ctx: RuleContext) -> RuleOutcome:
    """A GitHub suggestion is checked against its exact code, and that result is final: when the
    code changed some other way, a rename or other reading guessed from the suggestion's tokens
    is not reliable enough to decide (real-world dev case pydantic#9459)."""
    if requirement.suggested_code is not None:
        return suggestion_rule(requirement, ctx)
    return RULES.get(requirement.category, other_rule)(requirement, ctx)


__all__ = [
    "RULES",
    "Rule",
    "RuleContext",
    "RuleOutcome",
    "RuleStatus",
    "check_requirement",
]
