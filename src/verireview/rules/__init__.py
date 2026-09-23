"""Deterministic verification rules per requirement category (Phase 5)."""

from verireview.contracts import Requirement, RequirementCategory
from verireview.rules.api import api_rule
from verireview.rules.base import (
    Rule,
    RuleContext,
    RuleOutcome,
    RuleStatus,
    inconclusive,
)
from verireview.rules.errors import error_handling_rule
from verireview.rules.naming import naming_rule
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
    rule = RULES.get(requirement.category)
    if rule is None:
        return inconclusive(
            requirement, f"No verification rule exists for category '{requirement.category}'."
        )
    return rule(requirement, ctx)


__all__ = [
    "RULES",
    "Rule",
    "RuleContext",
    "RuleOutcome",
    "RuleStatus",
    "check_requirement",
]
