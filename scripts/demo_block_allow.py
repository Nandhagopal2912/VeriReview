"""Demo: VeriReview stops a bad resolve and allows a satisfied one.

Runs two real development cases through the real pipeline, the real policy (`policy.decide`) and
the real check-conclusion logic (`advisory.checks.conclusion_for`):

  * a BAD resolve:  the reviewer asked for email validation; the developer only wrote a docstring
                    and a log line that mention it;
  * a GOOD resolve: the reviewer asked for a None check; the developer added one.

Each case is shown twice:
  1. with today's real configuration (advisory: the check is neutral, nothing is ever blocked);
  2. as a SIMULATION with the four enforcement locks opened IN MEMORY for this run only
     (enforcement mode, the global switch, the case's category treated as eligible, and branch
     protection requiring the check).

Nothing on GitHub, in .env, in the database or in enforcement/eligibility.json changes. The same
path is pinned by the integration test test_check_fails_only_with_every_lock_open.

    python -m uv run python scripts/demo_block_allow.py
"""

from pathlib import Path
from types import SimpleNamespace

from verireview.advisory.checks import conclusion_for
from verireview.contracts import Verdict
from verireview.dataset.fixtures import load_fixture
from verireview.policy.decision import OperatingMode, PolicyConfig, configured_policy, decide
from verireview.verification import get_pipeline

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    (
        "BAD resolve",
        "validation-004-docstring-only",
        "Only wrote a docstring and a log line saying it validates the email.",
    ),
    (
        "GOOD resolve",
        "validation-001-none-check",
        "Added `if username is None: raise ValueError(...)` before saving.",
    ),
]
LINE = "-" * 78


def check_conclusion(action: str, policy: PolicyConfig) -> str:
    """What the posted check would conclude (the worker passes audit rows; only .action is read)."""
    return conclusion_for([SimpleNamespace(action=action)], policy)  # type: ignore[list-item]


def merge_outcome(conclusion: str) -> str:
    # GitHub treats a required check as passing when it ends success, neutral or skipped.
    if conclusion == "failure":
        return "MERGE BLOCKED  (the required VeriReview check failed)"
    return "MERGE ALLOWED  (the VeriReview check passed as neutral)"


def show(title: str, fixture_name: str, what_dev_did: str) -> None:
    fixture = load_fixture(ROOT / "dataset" / "fixtures" / fixture_name)
    result = get_pipeline().run(fixture.case)
    comment = fixture.case.thread.comments[0].body.strip()

    print(LINE)
    print(f"{title}: {fixture_name}")
    print(LINE)
    print(f"Reviewer asked : {comment}")
    print(f"Developer did  : {what_dev_did}")
    print(f"VeriReview     : {result.verdict.value} (confidence {result.confidence.value})")
    details = {e.id: e for e in result.evidence}
    for status in result.per_requirement:
        cited = [details[i] for i in status.evidence_ids if i in details]
        verdict_line = next(
            (e.detail for e in reversed(cited) if e.detail.startswith(status.requirement_id)),
            status.status.value,
        )
        where = next((e for e in reversed(cited) if e.location is not None), None)
        at = (
            f"  [{where.location.file}:{where.location.line_start}-{where.location.line_end}]"
            if where and where.location
            else ""
        )
        print(f"   {verdict_line}{at}")

    today = configured_policy()
    decision = decide(result, today)
    conclusion = check_conclusion(decision.action.value, today)
    print(
        f"\n  Today ({today.mode.value} mode):  action {decision.action.value}"
        f" -> check {conclusion} -> {merge_outcome(conclusion)}"
    )

    failed = {
        s.category
        for s in result.per_requirement
        if s.status == Verdict.NOT_SATISFIED and s.category
    }
    categories = failed or {s.category for s in result.per_requirement if s.category}
    simulated = PolicyConfig(
        mode=OperatingMode.ENFORCEMENT, allow_block=True, enforced_categories=frozenset(categories)
    )
    decision = decide(result, simulated)
    conclusion = check_conclusion(decision.action.value, simulated)
    print(
        f"  Simulation (all four locks open, in memory only):  action {decision.action.value}"
        f" -> check {conclusion} -> {merge_outcome(conclusion)}"
    )
    print(f"  Reason: {decision.reason}\n")


def main() -> None:
    print(
        "\nVeriReview: allow / block demo"
        " (real pipeline, real policy, locks opened in memory only)\n"
    )
    for title, name, what in CASES:
        show(title, name, what)
    print("Nothing was changed on GitHub, in .env, in the database or in eligibility.json.")
    print(
        "On the live system no category is eligible yet, so every check stays neutral (advisory)."
    )


if __name__ == "__main__":
    main()
