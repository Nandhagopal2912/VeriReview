"""Phase 2 placeholder: the whole comment is one uncategorised requirement.

Phase 4 replaces this with structured extraction (splitting, categories, targets).
"""

from verireview.contracts import Requirement, RequirementCategory, ReviewCase, ReviewRequirement


def whole_comment_requirement(case: ReviewCase) -> ReviewRequirement:
    return ReviewRequirement(
        case_id=case.case_id,
        target_file=case.file_path,
        requirements=[
            Requirement(
                id="R1",
                category=RequirementCategory.OTHER,
                description=case.thread.root.body.strip(),
            )
        ],
        source="stub",
    )
