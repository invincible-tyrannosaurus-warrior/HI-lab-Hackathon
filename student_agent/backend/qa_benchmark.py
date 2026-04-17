from __future__ import annotations

import hashlib
import json
from typing import Optional
from uuid import uuid4

from backend.llm_adapter import LLMClient
from backend.models import (
    CollaboratorHandoff,
    HandoffItem,
    LectureDeck,
    ProfileName,
    QAAnswerRecord,
    QABenchmarkRequest,
    QAImprovementResult,
    QAPassResult,
    QAQuestion,
)
from backend.storage import DECK_STORE, QA_BENCHMARK_STORE

QA_ANSWER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "student_answer": {"type": "string"},
        "confidence": {"type": "number"},
        "is_correct": {"type": "boolean"},
        "missed_concepts": {"type": "array", "items": {"type": "string"}},
        "failure_reason": {"type": "string"},
        "evidence_slide_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "student_answer",
        "confidence",
        "is_correct",
        "missed_concepts",
        "failure_reason",
        "evidence_slide_refs",
    ],
    "additionalProperties": False,
}


def run_qa_benchmark(
    request: QABenchmarkRequest,
    llm_client: Optional[LLMClient] = None,
) -> QAImprovementResult:
    DECK_STORE[request.deck.deck_id] = request.deck

    before_answers = [
        _answer_question(
            deck=request.deck,
            question=question,
            profile_name=request.profile_name,
            qa_support_content=request.qa_support_content,
            stage="before",
            use_mock=request.use_mock,
            llm_client=llm_client,
            provider_order=request.provider_order,
            allow_fallbacks=request.allow_fallbacks,
        )
        for question in request.questions
    ]
    after_answers = [
        _answer_question(
            deck=request.deck,
            question=question,
            profile_name=request.profile_name,
            qa_support_content=request.qa_support_content,
            stage="after",
            use_mock=request.use_mock,
            llm_client=llm_client,
            provider_order=request.provider_order,
            allow_fallbacks=request.allow_fallbacks,
        )
        for question in request.questions
    ]

    before_pass = _build_pass_result("before", before_answers)
    after_pass = _build_pass_result("after", after_answers)
    benchmark_id = f"benchmark_{uuid4().hex[:12]}"
    handoff = _build_handoff(
        benchmark_id=benchmark_id,
        deck_id=request.deck.deck_id,
        answers=after_answers,
        profile_name=request.profile_name,
        target_collaborator=request.target_collaborator,
    )

    result = QAImprovementResult(
        benchmark_id=benchmark_id,
        deck_id=request.deck.deck_id,
        profile_name=request.profile_name,
        total_questions=len(request.questions),
        model_used="mock_student_response" if request.use_mock else request.llm_model,
        before_pass=before_pass,
        after_pass=after_pass,
        improvement_delta=after_pass.correct_count - before_pass.correct_count,
        collaborator_handoff=handoff,
    )
    QA_BENCHMARK_STORE[result.benchmark_id] = result
    return result


def _build_pass_result(stage: str, answers: list[QAAnswerRecord]) -> QAPassResult:
    total = len(answers)
    correct_count = sum(1 for answer in answers if answer.is_correct)
    accuracy = correct_count / total if total else 0.0
    return QAPassResult(
        stage=stage,
        correct_count=correct_count,
        total_questions=total,
        accuracy=accuracy,
        answers=answers,
    )


def _build_handoff(
    benchmark_id: str,
    deck_id: str,
    answers: list[QAAnswerRecord],
    profile_name: ProfileName,
    target_collaborator: str,
) -> CollaboratorHandoff:
    unresolved_items = [
        HandoffItem(
            priority="high",
            target_ref=answer.question_id,
            issue_types=["incorrect_after_support", "content_revision_candidate"],
            affected_profiles=[profile_name],
            reason="Student still answered incorrectly after QA support in the after pass.",
            suggestion=(
                "Revise the related slide content to address the missed concepts, then regenerate or update the question support materials."
            ),
            question_id=answer.question_id,
            prompt=answer.prompt,
            student_answer=answer.student_answer,
            correct_answer=answer.correct_answer,
            failure_reason="Student still answered incorrectly after QA support.",
            missed_concepts=answer.missed_concepts,
            recommended_followup=(
                "Update the slide explanation, add a clearer worked example, and tighten terminology around the missed concepts."
            ),
            slide_refs=answer.evidence_slide_refs,
        )
        for answer in answers
        if not answer.is_correct
    ]
    return CollaboratorHandoff(
        handoff_id=f"handoff_{uuid4().hex[:12]}",
        benchmark_id=benchmark_id,
        deck_id=deck_id,
        target_collaborator=target_collaborator,
        unresolved_count=len(unresolved_items),
        items=unresolved_items,
    )


def _answer_question(
    deck: LectureDeck,
    question: QAQuestion,
    profile_name: ProfileName,
    qa_support_content: list[str],
    stage: str,
    use_mock: bool,
    llm_client: Optional[LLMClient] = None,
    provider_order: Optional[list[str]] = None,
    allow_fallbacks: bool = True,
) -> QAAnswerRecord:
    if not use_mock:
        if llm_client is None:
            raise RuntimeError("LLM client is required when use_mock is false.")
        return _real_answer_question(
            deck=deck,
            question=question,
            profile_name=profile_name,
            qa_support_content=qa_support_content,
            stage=stage,
            llm_client=llm_client,
            provider_order=provider_order,
            allow_fallbacks=allow_fallbacks,
        )

    is_correct = _mock_correctness(question, profile_name, qa_support_content, stage)
    student_answer = question.correct_answer if is_correct else _mock_wrong_answer(question, stage)
    missed_concepts = [] if is_correct else (question.concept_tags or ["concept_gap"])
    confidence = _mock_confidence(profile_name, stage, is_correct)
    evidence_slide_refs = question.slide_refs or _fallback_slide_refs(deck)

    return QAAnswerRecord(
        question_id=question.question_id,
        prompt=question.prompt,
        student_answer=student_answer,
        correct_answer=question.correct_answer,
        is_correct=is_correct,
        confidence=confidence,
        missed_concepts=missed_concepts,
        evidence_slide_refs=evidence_slide_refs,
    )


def _real_answer_question(
    deck: LectureDeck,
    question: QAQuestion,
    profile_name: ProfileName,
    qa_support_content: list[str],
    stage: str,
    llm_client: LLMClient,
    provider_order: Optional[list[str]] = None,
    allow_fallbacks: bool = True,
) -> QAAnswerRecord:
    payload = llm_client.generate_structured(
        system_prompt=_build_qa_system_prompt(profile_name),
        user_prompt=_build_qa_user_prompt(deck, question, qa_support_content, stage),
        response_schema=QA_ANSWER_JSON_SCHEMA,
        temperature=0.2,
        provider_order=provider_order,
        allow_fallbacks=allow_fallbacks,
    )

    try:
        student_answer = str(payload.get("student_answer", "")).strip()
        confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.5))))
        is_correct = bool(payload.get("is_correct", False))
        missed_concepts = [str(item) for item in payload.get("missed_concepts", [])]
        failure_reason = str(payload.get("failure_reason", ""))
        evidence_slide_refs = [str(item) for item in payload.get("evidence_slide_refs", [])]
    except Exception as exc:
        raise RuntimeError(f"Invalid QA model output: {exc}") from exc

    if not student_answer:
        student_answer = "No answer returned."

    return QAAnswerRecord(
        question_id=question.question_id,
        prompt=question.prompt,
        student_answer=student_answer,
        correct_answer=question.correct_answer,
        is_correct=is_correct,
        confidence=confidence,
        missed_concepts=[] if is_correct else (missed_concepts or question.concept_tags or ["concept_gap"]),
        evidence_slide_refs=evidence_slide_refs or question.slide_refs or _fallback_slide_refs(deck),
    )


def _build_qa_system_prompt(profile_name: ProfileName) -> str:
    return (
        "You are simulating a student taking a short concept-check assessment.\n"
        "Stay in student role and answer briefly.\n"
        "Then determine whether the student's answer matches the reference answer closely enough to count as correct.\n"
        "Return JSON only.\n"
        f"Student profile: {profile_name.value}"
    )


def _build_qa_user_prompt(
    deck: LectureDeck,
    question: QAQuestion,
    qa_support_content: list[str],
    stage: str,
) -> str:
    related_slides = [
        {
            "slide_id": slide.slide_id,
            "title": slide.title,
            "key_points": slide.key_points,
            "terms": slide.terms,
            "raw_text": slide.raw_text,
        }
        for slide in deck.slides
        if not question.slide_refs or slide.slide_id in question.slide_refs
    ]
    payload = {
        "stage": stage,
        "task": "answer question as student and judge correctness against the reference answer",
        "question": question.model_dump(),
        "deck_context": {
            "deck_id": deck.deck_id,
            "module_tag": deck.module_tag,
            "week_tag": deck.week_tag,
            "topic_tags": deck.topic_tags,
        },
        "related_slides": related_slides,
        "qa_support_content": qa_support_content if stage == "after" else [],
        "grading_rule": (
            "Mark is_correct true only when the student answer is semantically consistent with the correct answer."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _mock_correctness(
    question: QAQuestion,
    profile_name: ProfileName,
    qa_support_content: list[str],
    stage: str,
) -> bool:
    total_questions = 10
    rank = _stable_rank(question.question_id, total_questions)

    baseline_cutoff = {
        ProfileName.weak: 2,
        ProfileName.average: 4,
        ProfileName.strong: 7,
    }[profile_name]
    supported_cutoff = {
        ProfileName.weak: 6,
        ProfileName.average: 8,
        ProfileName.strong: 9,
    }[profile_name]

    if stage == "before":
        return rank < baseline_cutoff

    if profile_name == ProfileName.weak:
        return rank < 8

    support_bonus = min(1, len(qa_support_content) // 2)
    concept_bonus = 1 if question.concept_tags else 0
    return rank < min(total_questions, supported_cutoff + support_bonus + concept_bonus)


def _stable_rank(question_id: str, total_questions: int) -> int:
    digits = "".join(char for char in question_id if char.isdigit())
    if digits:
        return (int(digits) - 1) % total_questions
    return int(hashlib.sha256(question_id.encode()).hexdigest()[:8], 16) % total_questions


def _mock_wrong_answer(question: QAQuestion, stage: str) -> str:
    if stage == "after":
        return f"I still mix this up with {', '.join(question.concept_tags[:1] or ['a related concept'])}."
    return "I am not sure and would likely guess here."


def _mock_confidence(profile_name: ProfileName, stage: str, is_correct: bool) -> float:
    base = {
        ProfileName.weak: 0.32,
        ProfileName.average: 0.56,
        ProfileName.strong: 0.78,
    }[profile_name]
    if stage == "after":
        base += 0.18
    if not is_correct:
        base -= 0.14
    return max(0.0, min(1.0, round(base, 2)))


def _fallback_slide_refs(deck: LectureDeck) -> list[str]:
    if not deck.slides:
        return []
    return [deck.slides[0].slide_id]
