"""The worker loop survives unexpected errors (first live run: one error stopped all checking)."""

import logging
from typing import Any

import pytest

from verireview.advisory.worker import AdvisoryWorker
from verireview.policy import PolicyConfig


class StopLoopError(Exception):
    pass


def test_an_unexpected_error_does_not_stop_the_worker(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    worker = AdvisoryWorker(auth=Any, sessions=Any, policy=PolicyConfig())  # type: ignore[arg-type]
    outcomes: list[Any] = [RuntimeError("row vanished"), True, False]

    def run_once() -> bool:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return bool(outcome)

    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if not outcomes:
            raise StopLoopError

    monkeypatch.setattr(worker, "run_once", run_once)
    with caplog.at_level(logging.ERROR), pytest.raises(StopLoopError):
        worker.run_forever(0.5, sleep=sleep)

    assert outcomes == []  # it went on to the next jobs after the error
    assert sleeps == [0.5, 0.5]  # after the error, and when the queue was empty
    assert "unexpected error, continuing: RuntimeError" in caplog.text
    assert "row vanished" not in caplog.text  # only the class name is logged
