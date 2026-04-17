from __future__ import annotations

import json

from backend.models import EvaluationTask, LectureDeck, SlideBlock, StudentProfile


RUN_ANSWER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "main_answer": {"type": "string"},
        "confidence": {"type": "number"},
        "confusion_tags": {"type": "array", "items": {"type": "string"}},
        "missed_prerequisites": {"type": "array", "items": {"type": "string"}},
        "misconception_flags": {"type": "array", "items": {"type": "string"}},
        "evidence_slide_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "main_answer",
        "confidence",
        "confusion_tags",
        "missed_prerequisites",
        "misconception_flags",
        "evidence_slide_refs",
    ],
    "additionalProperties": False,
}


def build_system_prompt(profile: StudentProfile) -> str:
    rules = "\n".join(f"- {rule}" for rule in profile.behavior_rules)
    failures = "\n".join(f"- {mode}" for mode in profile.expected_failure_modes)
    return (
        "You are simulating a university student for controlled testing.\n"
        "Stay in student role only. Do not tutor, correct the material like a teacher, or give meta commentary.\n"
        "Be stable and repeatable: respond as the same profile would on repeated runs.\n"
        "Return JSON only that matches the required schema.\n"
        f"Profile: {profile.profile_name.value}\n"
        f"Prior knowledge: {profile.prior_knowledge}\n"
        f"Behavior rules:\n{rules}\n"
        f"Expected failure modes:\n{failures}"
    )


def slide_to_prompt_payload(slide: SlideBlock) -> dict:
    return {
        "slide_id": slide.slide_id,
        "title": slide.title,
        "key_points": slide.key_points,
        "terms": slide.terms,
        "examples": slide.examples,
        "raw_text": slide.raw_text,
    }


def build_user_prompt(deck: LectureDeck, slide: SlideBlock, task: EvaluationTask) -> str:
    payload = {
        "deck_id": deck.deck_id,
        "module_tag": deck.module_tag,
        "week_tag": deck.week_tag,
        "topic_tags": deck.topic_tags,
        "task_type": task.task_type.value,
        "instruction": task.instruction,
        "question_set": task.question_set,
        "slide_context": slide_to_prompt_payload(slide),
        "required_output_fields": [
            "main_answer",
            "confidence",
            "confusion_tags",
            "missed_prerequisites",
            "misconception_flags",
            "evidence_slide_refs",
        ],
    }
    return json.dumps(payload, indent=2)

