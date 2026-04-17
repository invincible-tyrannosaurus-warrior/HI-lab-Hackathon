from __future__ import annotations

import hashlib
from typing import Optional
from uuid import uuid4

from backend.llm_adapter import LLMClient
from backend.models import (
    EvidenceRef,
    EvaluationJob,
    EvaluationRun,
    EvaluationTask,
    LectureDeck,
    ProfileName,
    RunAnswer,
    RunStatus,
    StudentProfile,
    TaskType,
)
from backend.parsing import fallback_run_answer, parse_run_answer
from backend.prompting import RUN_ANSWER_JSON_SCHEMA, build_system_prompt, build_user_prompt
from backend.storage import DECK_STORE, JOB_STORE, RUN_STORE


def select_profiles(
    requested_profile_names: list[ProfileName],
    available_profiles: list[StudentProfile],
) -> list[StudentProfile]:
    profile_map = {profile.profile_name: profile for profile in available_profiles}
    return [profile_map[name] for name in requested_profile_names if name in profile_map]


def select_tasks(
    requested_task_types: list[TaskType],
    available_tasks: list[EvaluationTask],
) -> list[EvaluationTask]:
    task_map = {task.task_type: task for task in available_tasks}
    return [task_map[task_type] for task_type in requested_task_types if task_type in task_map]


def should_run_task(profile_name: ProfileName, task_type: TaskType) -> bool:
    if task_type == TaskType.coverage_check and profile_name != ProfileName.strong:
        return False
    return True


def run_evaluation_job(
    deck: LectureDeck,
    profiles: list[StudentProfile],
    tasks: list[EvaluationTask],
    llm_client: Optional[LLMClient] = None,
    use_mock: bool = True,
) -> EvaluationJob:
    job_id = f"job_{uuid4().hex[:12]}"
    DECK_STORE[deck.deck_id] = deck
    job = EvaluationJob(
        job_id=job_id,
        deck_id=deck.deck_id,
        profile_names=[profile.profile_name for profile in profiles],
        task_types=[task.task_type for task in tasks],
        status=RunStatus.running,
        run_ids=[],
    )
    JOB_STORE[job_id] = job

    try:
        for slide in deck.slides:
            for profile in profiles:
                for task in tasks:
                    if not should_run_task(profile.profile_name, task.task_type):
                        continue
                    run = EvaluationRun(
                        run_id=f"run_{uuid4().hex[:12]}",
                        deck_id=deck.deck_id,
                        slide_refs=[slide.slide_id],
                        student_profile=profile.profile_name,
                        task_type=task.task_type,
                        status=RunStatus.running,
                    )
                    RUN_STORE[run.run_id] = run
                    job.run_ids.append(run.run_id)

                    try:
                        answer = execute_run(
                            deck=deck,
                            slide=slide,
                            profile=profile,
                            task=task,
                            llm_client=llm_client,
                            use_mock=use_mock,
                        )
                        run.answer = answer
                        run.answer_text = answer.main_answer
                        run.confusion_tags = list(answer.confusion_tags)
                        run.missed_prerequisites = list(answer.missed_prerequisites)
                        run.misconception_flags = list(answer.misconception_flags)
                        run.evidence_refs = [
                            EvidenceRef(
                                run_id=run.run_id,
                                slide_refs=answer.evidence_slide_refs or run.slide_refs,
                                task_type=run.task_type,
                                student_profile=run.student_profile,
                            )
                        ]
                        run.status = RunStatus.completed
                    except Exception as exc:
                        run.answer = fallback_run_answer(str(exc), [slide.slide_id])
                        run.answer_text = run.answer.main_answer
                        run.confusion_tags = list(run.answer.confusion_tags)
                        run.missed_prerequisites = list(run.answer.missed_prerequisites)
                        run.misconception_flags = list(run.answer.misconception_flags)
                        run.evidence_refs = [
                            EvidenceRef(
                                run_id=run.run_id,
                                slide_refs=run.answer.evidence_slide_refs or [slide.slide_id],
                                task_type=run.task_type,
                                student_profile=run.student_profile,
                            )
                        ]
                        run.error_message = str(exc)
                        run.status = RunStatus.failed

        job.status = (
            RunStatus.completed
            if all(RUN_STORE[run_id].status in {RunStatus.completed, RunStatus.failed} for run_id in job.run_ids)
            else RunStatus.failed
        )
    except Exception:
        job.status = RunStatus.failed
        raise

    JOB_STORE[job_id] = job
    return job


def execute_run(
    deck: LectureDeck,
    slide,
    profile: StudentProfile,
    task: EvaluationTask,
    llm_client: Optional[LLMClient] = None,
    use_mock: bool = True,
) -> RunAnswer:
    if use_mock or llm_client is None:
        return mock_student_response(deck, slide.slide_id, profile, task)
    return real_student_response(deck, slide, profile, task, llm_client)


def mock_student_response(
    deck: LectureDeck,
    slide_id: str,
    profile: StudentProfile,
    task: EvaluationTask,
) -> RunAnswer:
    slide = next(slide for slide in deck.slides if slide.slide_id == slide_id)
    text_blob = " ".join(
        [
            slide.title,
            " ".join(slide.key_points),
            " ".join(slide.terms),
            " ".join(slide.examples),
            slide.raw_text or "",
        ]
    ).lower()
    seed = int(hashlib.sha256(f"{deck.deck_id}:{slide_id}:{profile.profile_name}:{task.task_type}".encode()).hexdigest()[:8], 16)

    confusion_tags: list[str] = []
    missed_prerequisites: list[str] = []
    misconception_flags: list[str] = []

    if "supervised" in text_blob:
        confusion_tags.append("label_usage")
    if "model" in text_blob or "algorithm" in text_blob:
        missed_prerequisites.append("basic_statistics")
    if "pattern" in text_blob:
        confusion_tags.append("pattern_definition")
    if task.task_type == TaskType.confusion_report and "example" not in text_blob:
        confusion_tags.append("needs_worked_example")
    if task.task_type == TaskType.coverage_check:
        misconception_flags.append("missing_boundary_conditions")
    if profile.profile_name == ProfileName.weak:
        confusion_tags.append("terminology_overload")
        if slide.terms:
            missed_prerequisites.append(slide.terms[0])
    elif profile.profile_name == ProfileName.average:
        confusion_tags.append("pace_jump")
    else:
        misconception_flags.append("oversimplified_explanation")
        if not slide.examples:
            misconception_flags.append("missing_counterexample")

    confidence_base = {
        ProfileName.weak: 0.35,
        ProfileName.average: 0.62,
        ProfileName.strong: 0.81,
    }[profile.profile_name]
    confidence = max(0.0, min(1.0, confidence_base + (seed % 7 - 3) * 0.02))

    main_answer = _build_mock_main_answer(slide, profile.profile_name, task.task_type, confusion_tags, misconception_flags)

    return RunAnswer(
        main_answer=main_answer,
        confidence=confidence,
        confusion_tags=_dedupe(confusion_tags),
        missed_prerequisites=_dedupe(missed_prerequisites),
        misconception_flags=_dedupe(misconception_flags),
        evidence_slide_refs=[slide.slide_id],
    )


def real_student_response(
    deck: LectureDeck,
    slide,
    profile: StudentProfile,
    task: EvaluationTask,
    llm_client: LLMClient,
) -> RunAnswer:
    system_prompt = build_system_prompt(profile)
    user_prompt = build_user_prompt(deck, slide, task)
    payload = llm_client.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=RUN_ANSWER_JSON_SCHEMA,
        temperature=0.2,
    )
    return parse_run_answer(payload, fallback_slide_refs=[slide.slide_id])


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _build_mock_main_answer(
    slide,
    profile_name: ProfileName,
    task_type: TaskType,
    confusion_tags: list[str],
    misconception_flags: list[str],
) -> str:
    intro_map = {
        ProfileName.weak: "I think this slide is saying",
        ProfileName.average: "My understanding is that",
        ProfileName.strong: "The slide argues that",
    }
    uncertainty = ""
    if profile_name == ProfileName.weak and confusion_tags:
        uncertainty = f" but I get stuck on {confusion_tags[0].replace('_', ' ')}"
    if profile_name == ProfileName.strong and misconception_flags:
        uncertainty = f" and it may be incomplete because of {misconception_flags[0].replace('_', ' ')}"

    if task_type == TaskType.confusion_report:
        return (
            f"{intro_map[profile_name]} {slide.title.lower()}, but the pacing feels uneven"
            f"{uncertainty}. I would want one more concrete example."
        )
    if task_type == TaskType.coverage_check:
        return (
            f"{intro_map[profile_name]} {slide.title.lower()}, but the explanation could add missing assumptions,"
            " caveats, and a boundary case."
        )
    return f"{intro_map[profile_name]} {slide.title.lower()}{uncertainty}."
