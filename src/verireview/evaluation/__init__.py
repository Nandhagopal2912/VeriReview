"""Evaluation harness: metrics and fixture/benchmark runners (plan §20)."""

from verireview.evaluation.metrics import Metrics, compute_metrics
from verireview.evaluation.runner import EvaluationReport, dataset_hash, evaluate

__all__ = ["EvaluationReport", "Metrics", "compute_metrics", "dataset_hash", "evaluate"]
