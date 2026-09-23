"""Run one rule on small before/after snippets, with an explicit requirement (no extraction)."""

from textwrap import dedent

from helpers.cases import make_case
from verireview.contracts import Requirement, RequirementCategory, ReviewRequirement
from verireview.rules import RuleContext, RuleOutcome, check_requirement


def req(
    category: RequirementCategory,
    description: str,
    target: str | None = None,
    condition: str | None = None,
    suggested_code: str | None = None,
) -> Requirement:
    return Requirement(
        id="R1",
        category=category,
        description=description,
        target=target,
        condition=condition,
        suggested_code=suggested_code,
    )


def run_rule(
    requirement: Requirement,
    before: str,
    after: str,
    anchor: int,
    comment: str | None = None,
    tests_before: dict[str, str] | None = None,
    tests_after: dict[str, str] | None = None,
) -> RuleOutcome:
    case = make_case(dedent(before).lstrip("\n"), dedent(after).lstrip("\n"), anchor)
    case = case.model_copy(
        update={
            "thread": case.thread.model_copy(
                update={
                    "comments": [
                        case.thread.comments[0].model_copy(
                            update={"body": comment or requirement.description}
                        )
                    ]
                }
            ),
            "test_files": {p: dedent(c).lstrip("\n") for p, c in (tests_after or {}).items()},
            "test_files_before": {
                p: dedent(c).lstrip("\n") for p, c in (tests_before or {}).items()
            },
        }
    )
    requirement_set = ReviewRequirement(
        case_id="c", target_file="m.py", requirements=[requirement], source="manual"
    )
    ctx = RuleContext.build(case, requirement_set)
    assert ctx is not None
    return check_requirement(requirement, ctx)


def kinds(outcome: RuleOutcome) -> dict[str, bool | None]:
    return {e.kind: e.passed for e in outcome.evidence}
