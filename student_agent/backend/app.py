from __future__ import annotations

from fastapi import FastAPI, HTTPException

from backend.aggregation import aggregate_runs_for_deck
from backend.llm_adapter import OpenRouterLLMClient
from backend.models import PPTXIngestRequest, QABenchmarkRequest, RunEvaluationRequest
from backend.pptx_parser import pptx_to_lecture_deck
from backend.qa_benchmark import run_qa_benchmark
from backend.profiles import DEFAULT_PROFILES
from backend.runner import run_evaluation_job, select_profiles, select_tasks
from backend.storage import DECK_STORE, JOB_STORE, QA_BENCHMARK_STORE, RUN_STORE, SIGNAL_STORE
from backend.tasks import DEFAULT_TASKS

app = FastAPI(title="Student Agent Testing MVP", version="0.1.0")


@app.get("/")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "student-agent-testing"}


@app.post("/evaluation/run")
def run_evaluation(request: RunEvaluationRequest) -> dict:
    profiles = select_profiles(request.profile_names, DEFAULT_PROFILES)
    tasks = select_tasks(request.task_types, DEFAULT_TASKS)
    llm_client = None if request.use_mock else OpenRouterLLMClient()

    job = run_evaluation_job(
        deck=request.deck,
        profiles=profiles,
        tasks=tasks,
        llm_client=llm_client,
        use_mock=request.use_mock,
    )

    summary = None
    if request.auto_aggregate and job.status.value == "completed":
        summary = aggregate_runs_for_deck(request.deck.deck_id)
        job.summary_ready = True
        JOB_STORE[job.job_id] = job

    return {"job": job, "summary": summary}


@app.post("/deck/ingest/pptx")
def ingest_pptx(request: PPTXIngestRequest) -> dict:
    deck = pptx_to_lecture_deck(
        pptx_path=request.pptx_path,
        deck_id=request.deck_id,
        module_tag=request.module_tag,
        week_tag=request.week_tag,
        topic_tags=request.topic_tags,
    )
    DECK_STORE[deck.deck_id] = deck
    return {"deck": deck}


@app.post("/evaluation/run-pptx")
def run_evaluation_from_pptx(
    request: PPTXIngestRequest,
    use_mock: bool = True,
    auto_aggregate: bool = True,
) -> dict:
    deck = pptx_to_lecture_deck(
        pptx_path=request.pptx_path,
        deck_id=request.deck_id,
        module_tag=request.module_tag,
        week_tag=request.week_tag,
        topic_tags=request.topic_tags,
    )
    run_request = RunEvaluationRequest(deck=deck, auto_aggregate=auto_aggregate, use_mock=use_mock)
    return run_evaluation(run_request)


@app.post("/evaluation/qa-improvement")
def evaluate_qa_improvement(request: QABenchmarkRequest):
    try:
        llm_client = None if request.use_mock else OpenRouterLLMClient(model=request.llm_model)
        return run_qa_benchmark(request, llm_client=llm_client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"QA improvement failed: {exc}") from exc


@app.get("/evaluation/qa-improvement/{benchmark_id}")
def get_qa_improvement_result(benchmark_id: str):
    result = QA_BENCHMARK_STORE.get(benchmark_id)
    if result is None:
        raise HTTPException(status_code=404, detail="QA benchmark not found")
    return result


@app.get("/evaluation/{job_id}")
def get_job_status(job_id: str) -> dict:
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    runs = [RUN_STORE[run_id] for run_id in job.run_ids if run_id in RUN_STORE]
    return {"job": job, "runs": runs}


@app.get("/evaluation/results/{run_id}")
def get_run_result(run_id: str):
    run = RUN_STORE.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/evaluation/summary/{deck_id}")
def get_summary(deck_id: str):
    if deck_id in SIGNAL_STORE:
        return SIGNAL_STORE[deck_id]
    try:
        return aggregate_runs_for_deck(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deck or summary not found") from exc
