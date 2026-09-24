import pytest
from pydantic import ValidationError

from helpers.cases import make_case
from verireview.config import Settings
from verireview.contracts import (
    Confidence,
    RequirementCategory,
    RequirementStatus,
    Verdict,
    VerificationResult,
)
from verireview.policy import Action, OperatingMode, PolicyConfig, configured_policy, decide

CASE_ID = make_case("x = 1\n", "x = 2\n", 1).case_id


def result(verdict: Verdict, confidence: Confidence) -> VerificationResult:
    return VerificationResult(
        case_id=CASE_ID,
        verdict=verdict,
        confidence=confidence,
        per_requirement=[],
        evidence=[],
        explanation="x",
        pipeline_version="test",
    )


V, C, A, RC = Verdict, Confidence, Action, RequirementCategory


@pytest.mark.parametrize(
    ("verdict", "confidence", "recommended"),
    [
        (V.SATISFIED, C.HIGH, A.ALLOW),
        (V.SATISFIED, C.MEDIUM, A.ALLOW),
        (V.SATISFIED, C.LOW, A.HUMAN_REVIEW),
        (V.PARTIALLY_SATISFIED, C.MEDIUM, A.HUMAN_REVIEW),
        (V.UNCERTAIN, C.LOW, A.HUMAN_REVIEW),
        (V.NOT_SATISFIED, C.MEDIUM, A.BLOCK),
        (V.NOT_SATISFIED, C.LOW, A.HUMAN_REVIEW),
    ],
)
def test_plan_section_4_mapping(
    verdict: Verdict, confidence: Confidence, recommended: Action
) -> None:
    assert decide(result(verdict, confidence)).recommended == recommended


def test_block_is_downgraded_to_warn_by_default() -> None:
    decision = decide(result(V.NOT_SATISFIED, C.MEDIUM))

    assert decision.recommended == A.BLOCK
    assert decision.action == A.WARN
    assert not decision.blocks_merge
    assert "Blocking is disabled" in decision.reason


def failed(*categories: RC | None) -> VerificationResult:
    """NOT_SATISFIED at MEDIUM with one failed requirement per category."""
    return result(V.NOT_SATISFIED, C.MEDIUM).model_copy(
        update={
            "per_requirement": [
                RequirementStatus(
                    requirement_id=f"R{i}", status=V.NOT_SATISFIED, evidence_ids=[], category=c
                )
                for i, c in enumerate(categories, 1)
            ]
        }
    )


def test_blocking_needs_enforcement_mode_explicit_opt_in_and_an_enforced_category() -> None:
    enforced = PolicyConfig(
        mode=OperatingMode.ENFORCEMENT, allow_block=True, enforced_categories=frozenset({RC.NAMING})
    )
    enforcement_without_opt_in = PolicyConfig(
        mode=OperatingMode.ENFORCEMENT, enforced_categories=frozenset({RC.NAMING})
    )

    assert decide(failed(RC.NAMING), enforced).blocks_merge
    assert not decide(failed(RC.NAMING), enforcement_without_opt_in).blocks_merge


def test_category_lock_blocks_only_when_every_failed_requirement_is_enforced() -> None:
    enforced = PolicyConfig(
        mode=OperatingMode.ENFORCEMENT, allow_block=True, enforced_categories=frozenset({RC.NAMING})
    )

    assert decide(failed(RC.NAMING, RC.NAMING), enforced).action == A.BLOCK
    mixed = decide(failed(RC.NAMING, RC.VALIDATION), enforced)
    assert (mixed.action, mixed.blocks_merge) == (A.WARN, False)
    assert "category approved for enforcement" in mixed.reason
    assert not decide(failed(None), enforced).blocks_merge  # unknown category never blocks
    assert not decide(result(V.NOT_SATISFIED, C.MEDIUM), enforced).blocks_merge  # no statuses


def test_enforcement_without_categories_never_blocks() -> None:
    config = PolicyConfig(mode=OperatingMode.ENFORCEMENT, allow_block=True)

    for category in RC:
        assert not decide(failed(category), config).blocks_merge


def test_settings_categories_are_cut_to_the_shipped_eligibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        policy_mode="enforcement",
        policy_allow_block=True,
        policy_enforced_categories="naming,validation",  # type: ignore[arg-type]
    )
    monkeypatch.setattr("verireview.policy.decision.get_settings", lambda: settings)

    # The shipped eligibility admits no category (Phase 12), so nothing is enforced.
    assert configured_policy().enforced_categories == frozenset()
    assert not decide(failed(RC.NAMING), configured_policy()).blocks_merge


def test_allow_block_outside_enforcement_is_rejected() -> None:
    with pytest.raises(ValidationError, match="enforcement"):
        PolicyConfig(mode=OperatingMode.ADVISORY, allow_block=True)


def test_observe_mode_posts_nothing() -> None:
    decision = decide(result(V.SATISFIED, C.MEDIUM), PolicyConfig(mode=OperatingMode.OBSERVE))

    assert not decision.posts_to_github


def test_human_review_mode_turns_warnings_into_reviews() -> None:
    decision = decide(
        result(V.NOT_SATISFIED, C.MEDIUM), PolicyConfig(mode=OperatingMode.HUMAN_REVIEW)
    )

    assert decision.action == A.HUMAN_REVIEW


def test_default_configuration_never_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Safety pin (plan §4, Phase 12): advisory mode and no blocking unless deliberately changed."""
    defaults = Settings(_env_file=None)
    monkeypatch.setattr("verireview.policy.decision.get_settings", lambda: defaults)

    config = configured_policy()

    assert (config.mode, config.allow_block) == (OperatingMode.ADVISORY, False)
    for verdict in Verdict:
        for confidence in Confidence:
            assert not decide(result(verdict, confidence), config).blocks_merge
