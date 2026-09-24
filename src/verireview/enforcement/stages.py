"""Per-repository rollout stages (plan §27, roadmap Phase 12).

    observe ─► advisory ─► human_review ─► enforcement
    (audit only)  (neutral check)  (+ "Confirm reviewed")  (may fail the check, eligible categories)

Rules, all enforced here and pinned by tests:

- **Opt-in per repository.** A repository without a row runs at the global default mode, clamped
  to ``human_review``: no global setting alone can make any repository enforce.
- **One stage at a time upwards.** Demotion (rollback) is always allowed, to any stage.
- **Entering enforcement** needs: the repository at ``human_review`` for at least
  ``enforcement_min_human_review_days`` with at least ``enforcement_min_confirmations`` reviewer
  confirmations since, and a non-empty list of categories that are all *eligible* on the frozen
  test evidence (``eligibility.py``; none today).
- **Every change is recorded** (who, when, from, to, categories, reason) in an append-only table.

Even in enforcement, a check only fails when the global ``policy_allow_block`` is on, and it only
blocks merging if the repository owner made the check required in branch protection.
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verireview.contracts import RequirementCategory
from verireview.db.models import RepositoryPolicy, RepositoryPolicyChange, ReviewConfirmation
from verireview.policy import OperatingMode, PolicyConfig

STAGES = (
    OperatingMode.OBSERVE,
    OperatingMode.ADVISORY,
    OperatingMode.HUMAN_REVIEW,
    OperatingMode.ENFORCEMENT,
)
IMPLICIT_STAGE = OperatingMode.ADVISORY  # a repository without a row
MAX_WITHOUT_OPT_IN = OperatingMode.HUMAN_REVIEW


class StageChangeError(ValueError):
    """A stage change that the rollout rules do not allow (the message says which rule)."""


def current(session: Session, installation_id: int, repository: str) -> RepositoryPolicy | None:
    return session.scalars(
        select(RepositoryPolicy).where(
            RepositoryPolicy.installation_id == installation_id,
            RepositoryPolicy.repository == repository,
        )
    ).first()


def effective_policy(
    session: Session,
    installation_id: int,
    repository: str,
    default: PolicyConfig,
    eligible: frozenset[RequirementCategory],
) -> PolicyConfig:
    """The policy for one repository: its opted-in stage, or the clamped global default."""
    row = current(session, installation_id, repository)
    if row is None:
        mode = min(default.mode, MAX_WITHOUT_OPT_IN, key=STAGES.index)
        return PolicyConfig(mode=mode)
    mode = OperatingMode(row.stage)
    if mode != OperatingMode.ENFORCEMENT:
        return PolicyConfig(mode=mode)
    categories = {RequirementCategory(c) for c in row.enforced_categories}
    return PolicyConfig(
        mode=mode,
        allow_block=default.allow_block,
        enforced_categories=frozenset(categories & eligible),
    )


def change_stage(
    session: Session,
    installation_id: int,
    repository: str,
    to_stage: OperatingMode,
    *,
    actor: str,
    reason: str,
    eligible: frozenset[RequirementCategory],
    categories: Iterable[RequirementCategory] = (),
    min_days: int = 14,
    min_confirmations: int = 10,
    now: datetime | None = None,
) -> RepositoryPolicy:
    now = now or datetime.now(UTC)
    wanted = sorted(set(categories), key=list(RequirementCategory).index)
    if not actor.strip() or len(reason.strip()) < 10:
        raise StageChangeError("an actor and a reason (at least 10 characters) are required")

    row = current(session, installation_id, repository)
    from_stage = OperatingMode(row.stage) if row else IMPLICIT_STAGE
    if STAGES.index(to_stage) > STAGES.index(from_stage) + 1:
        raise StageChangeError(
            f"promote one stage at a time: {from_stage.value} → "
            f"{STAGES[STAGES.index(from_stage) + 1].value}, not {to_stage.value}"
        )
    if to_stage != OperatingMode.ENFORCEMENT and wanted:
        raise StageChangeError("categories only apply to the enforcement stage")
    if to_stage == OperatingMode.ENFORCEMENT and from_stage != OperatingMode.ENFORCEMENT:
        _check_enforcement_entry(
            session,
            installation_id,
            repository,
            row,
            wanted,
            eligible,
            min_days,
            min_confirmations,
            now,
        )
    elif to_stage == OperatingMode.ENFORCEMENT:
        _check_categories(wanted, eligible)

    existed = row is not None
    if row is None:
        row = RepositoryPolicy(installation_id=installation_id, repository=repository)
        session.add(row)
    if row.stage != to_stage.value:
        row.stage_since = now
    row.stage = to_stage.value
    row.enforced_categories = [c.value for c in wanted]
    row.updated_by = actor
    session.add(
        RepositoryPolicyChange(
            installation_id=installation_id,
            repository=repository,
            from_stage=from_stage.value if existed else None,
            to_stage=to_stage.value,
            enforced_categories=[c.value for c in wanted],
            actor=actor,
            reason=reason.strip(),
        )
    )
    session.commit()
    return row


def _check_categories(
    wanted: list[RequirementCategory], eligible: frozenset[RequirementCategory]
) -> None:
    if not wanted:
        raise StageChangeError("enforcement needs at least one category")
    not_eligible = [c.value for c in wanted if c not in eligible]
    if not_eligible:
        raise StageChangeError(
            f"not eligible on the frozen test evidence: {', '.join(not_eligible)} "
            f"(eligible now: {', '.join(sorted(c.value for c in eligible)) or 'none'})"
        )


def _check_enforcement_entry(
    session: Session,
    installation_id: int,
    repository: str,
    row: RepositoryPolicy | None,
    wanted: list[RequirementCategory],
    eligible: frozenset[RequirementCategory],
    min_days: int,
    min_confirmations: int,
    now: datetime,
) -> None:
    _check_categories(wanted, eligible)
    if row is None or row.stage != OperatingMode.HUMAN_REVIEW.value:
        raise StageChangeError("enforcement can only follow the human_review stage")
    held = now - row.stage_since
    if held < timedelta(days=min_days):
        raise StageChangeError(
            f"human review has run {held.days} day(s); at least {min_days} are required"
        )
    confirmations = confirmations_since(session, installation_id, repository, row.stage_since)
    if confirmations < min_confirmations:
        raise StageChangeError(
            f"{confirmations} reviewer confirmation(s) during human review; "
            f"at least {min_confirmations} are required"
        )


def confirmations_since(
    session: Session, installation_id: int, repository: str, since: datetime
) -> int:
    return int(
        session.scalar(
            select(func.count(ReviewConfirmation.id)).where(
                ReviewConfirmation.installation_id == installation_id,
                ReviewConfirmation.repository == repository,
                ReviewConfirmation.created_at >= since,
            )
        )
        or 0
    )
