from __future__ import annotations

from backend.models import AggregatedSignal, EvaluationJob, EvaluationRun, LectureDeck, QAImprovementResult


DECK_STORE: dict[str, LectureDeck] = {}
JOB_STORE: dict[str, EvaluationJob] = {}
RUN_STORE: dict[str, EvaluationRun] = {}
SIGNAL_STORE: dict[str, AggregatedSignal] = {}
QA_BENCHMARK_STORE: dict[str, QAImprovementResult] = {}
