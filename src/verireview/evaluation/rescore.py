"""Re-score a recorded benchmark run against the labels the dataset holds now.

When real-world gold changes after a run (humans replace provisional model labels), the run's
stored predictions are scored again; no verifier runs, so a used test split stays used once.
Three slices are reported, pooled and for the real-world cases alone:

- ``recorded``: the run as it was scored (every recorded case, the labels of that time);
- ``same_cases_recorded_labels`` / ``same_cases_current_labels``: the cases that are still
  included now, scored with the old and with the current labels. These two are comparable.

Cases excluded by the current labels drop out. Cases the current labels include but the run
never saw have no stored prediction and are listed, not scored.
"""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel

from verireview.contracts import Verdict
from verireview.evaluation.benchmark import CaseRecord, SliceResult, slice_result

REAL_WORLD = "real_world"


class LabelChange(BaseModel):
    case_id: str
    recorded: Verdict
    current: Verdict
    predicted: Verdict


class RescoredSlices(BaseModel):
    recorded: SliceResult
    same_cases_recorded_labels: SliceResult
    same_cases_current_labels: SliceResult


class Rescore(BaseModel):
    system: str
    source_report: str
    label_sources: dict[str, int]  # of the current real-world labels, e.g. {"human": 60}
    pooled: RescoredSlices
    real_world: RescoredSlices
    now_excluded: list[str]
    included_without_prediction: list[str]
    label_changes: list[LabelChange]


def rescore(
    records: Sequence[CaseRecord],
    current: Mapping[str, Verdict | None],
    resamples: int,
) -> tuple[RescoredSlices, RescoredSlices, list[str], list[str], list[LabelChange]]:
    """``current`` maps a real-world case id to its current verdict (None = excluded now).

    A real-world record whose id is not in ``current`` keeps its recorded label.
    """
    kept: list[CaseRecord] = []
    relabelled: list[CaseRecord] = []
    excluded: list[str] = []
    changes: list[LabelChange] = []
    for record in records:
        if record.source != REAL_WORLD or record.case_id not in current:
            kept.append(record)
            relabelled.append(record)
            continue
        verdict = current[record.case_id]
        if verdict is None:
            excluded.append(record.case_id)
            continue
        kept.append(record)
        relabelled.append(record.model_copy(update={"expected": verdict}))
        if verdict != record.expected:
            changes.append(
                LabelChange(
                    case_id=record.case_id,
                    recorded=record.expected,
                    current=verdict,
                    predicted=record.predicted,
                )
            )
    seen = {r.case_id for r in records}
    unseen = sorted(i for i, verdict in current.items() if verdict is not None and i not in seen)

    def slices(only_real_world: bool) -> RescoredSlices:
        def pick(rows: Sequence[CaseRecord]) -> list[CaseRecord]:
            return [r for r in rows if not only_real_world or r.source == REAL_WORLD]

        return RescoredSlices(
            recorded=slice_result(pick(records), resamples),
            same_cases_recorded_labels=slice_result(pick(kept), resamples),
            same_cases_current_labels=slice_result(pick(relabelled), resamples),
        )

    return slices(False), slices(True), sorted(excluded), unseen, changes
