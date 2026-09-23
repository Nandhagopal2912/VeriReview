import pytest
from pydantic import ValidationError

from helpers.cases import make_case
from verireview.config import Settings
from verireview.contracts import Confidence, Verdict, VerificationResult
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


V, C, A = Verdict, Confidence, Action


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


def test_blocking_needs_enforcement_mode_and_explicit_opt_in() -> None:
    enforced = PolicyConfig(mode=OperatingMode.ENFORCEMENT, allow_block=True)
    enforcement_without_opt_in = PolicyConfig(mode=OperatingMode.ENFORCEMENT)

    assert decide(result(V.NOT_SATISFIED, C.MEDIUM), enforced).blocks_merge
    assert not decide(result(V.NOT_SATISFIED, C.MEDIUM), enforcement_without_opt_in).blocks_merge


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
