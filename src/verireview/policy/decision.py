"""Policy layer (plan §4, §27): what GitHub should do with a verification result.

Verification results are *not* enforcement decisions. This layer maps (verdict, confidence) to an
action, then applies the operating mode:

    verdict               confidence      action
    SATISFIED             HIGH / MEDIUM   ALLOW
    SATISFIED             LOW             HUMAN_REVIEW
    PARTIALLY_SATISFIED   any             HUMAN_REVIEW
    UNCERTAIN             any             HUMAN_REVIEW
    NOT_SATISFIED         HIGH / MEDIUM   BLOCK  → downgraded to WARN unless blocking is enabled
    NOT_SATISFIED         LOW             HUMAN_REVIEW

Operating modes (plan §27): OBSERVE (analyse only, nothing posted), ADVISORY (post, never
block), HUMAN_REVIEW (require reviewer confirmation), ENFORCEMENT (may block). Blocking needs
ENFORCEMENT mode *and* ``allow_block``. Both are off by default, and the plan forbids enabling
them before Phase 12's evaluation.

Phase 12 adds a third lock: a BLOCK also needs **every** not-satisfied requirement to be in an
``enforced_categories`` category, and those can only be categories the frozen test evidence
makes eligible (``enforcement.eligibility``; none today). Anything else is downgraded to a
warning. The fourth lock is outside VeriReview: the repository must make the check required.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from verireview.config import get_settings
from verireview.contracts import Confidence, RequirementCategory, Verdict, VerificationResult


class Action(StrEnum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCK = "BLOCK"


class OperatingMode(StrEnum):
    OBSERVE = "observe"
    ADVISORY = "advisory"
    HUMAN_REVIEW = "human_review"
    ENFORCEMENT = "enforcement"


class PolicyConfig(BaseModel):
    mode: OperatingMode = OperatingMode.ADVISORY
    allow_block: bool = False
    enforced_categories: frozenset[RequirementCategory] = frozenset()

    @model_validator(mode="after")
    def _block_needs_enforcement(self) -> Self:
        if self.allow_block and self.mode != OperatingMode.ENFORCEMENT:
            raise ValueError("allow_block requires mode=enforcement")
        return self


class PolicyDecision(BaseModel):
    action: Action
    recommended: Action  # before the operating mode was applied
    mode: OperatingMode
    posts_to_github: bool
    blocks_merge: bool
    reason: str


def configured_policy() -> PolicyConfig:
    """Policy from settings (VERIREVIEW_POLICY_MODE / _ALLOW_BLOCK / _ENFORCED_CATEGORIES).

    Enforced categories are intersected with the shipped eligibility: a category the frozen test
    evidence does not support is dropped, whatever the settings say.
    """
    from verireview.enforcement.eligibility import eligible_categories

    settings = get_settings()
    requested = {RequirementCategory(c) for c in settings.policy_enforced_categories}
    return PolicyConfig(
        mode=OperatingMode(settings.policy_mode),
        allow_block=settings.policy_allow_block,
        enforced_categories=frozenset(requested & eligible_categories()),
    )


def decide(result: VerificationResult, config: PolicyConfig | None = None) -> PolicyDecision:
    config = config or PolicyConfig()
    recommended, reason = _recommend(result.verdict, result.confidence)

    action = recommended
    if action == Action.BLOCK and not (
        config.allow_block and config.mode == OperatingMode.ENFORCEMENT
    ):
        action = Action.WARN
        reason += " Blocking is disabled, so this is reported as a warning."
    elif action == Action.BLOCK and not _all_enforced(result, config.enforced_categories):
        action = Action.WARN
        reason += (
            " Not every failed requirement is in a category approved for enforcement, so this"
            " is reported as a warning."
        )
    if config.mode == OperatingMode.HUMAN_REVIEW and action in (Action.WARN, Action.BLOCK):
        action = Action.HUMAN_REVIEW
        reason += " Human-review mode: a reviewer confirms before anything is enforced."

    return PolicyDecision(
        action=action,
        recommended=recommended,
        mode=config.mode,
        posts_to_github=config.mode != OperatingMode.OBSERVE,
        blocks_merge=action == Action.BLOCK,
        reason=reason,
    )


def _all_enforced(result: VerificationResult, enforced: frozenset[RequirementCategory]) -> bool:
    """Every NOT_SATISFIED requirement has a known category that is enforced (none → False)."""
    failed = [s.category for s in result.per_requirement if s.status == Verdict.NOT_SATISFIED]
    return bool(failed) and all(c is not None and c in enforced for c in failed)


def _recommend(verdict: Verdict, confidence: Confidence) -> tuple[Action, str]:
    strong = confidence in (Confidence.HIGH, Confidence.MEDIUM)
    match verdict:
        case Verdict.SATISFIED if strong:
            return Action.ALLOW, "The requirement appears satisfied."
        case Verdict.SATISFIED:
            return Action.HUMAN_REVIEW, "Satisfied, but the evidence is not reliable enough."
        case Verdict.NOT_SATISFIED if strong:
            return Action.BLOCK, "The requirement does not appear to be satisfied."
        case Verdict.NOT_SATISFIED:
            return Action.HUMAN_REVIEW, "Probably not satisfied, but the evidence is weak."
        case Verdict.PARTIALLY_SATISFIED:
            return Action.HUMAN_REVIEW, "Only part of the request appears satisfied."
        case _:
            return Action.HUMAN_REVIEW, "The verifier could not decide."
