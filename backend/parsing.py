from __future__ import annotations

from backend.models import RunAnswer


def parse_run_answer(payload: dict, fallback_slide_refs: list[str]) -> RunAnswer:
    try:
        return RunAnswer.model_validate(payload)
    except Exception:
        return fallback_run_answer(
            message="Model output could not be parsed into the expected schema.",
            slide_refs=fallback_slide_refs,
        )


def fallback_run_answer(message: str, slide_refs: list[str]) -> RunAnswer:
    return RunAnswer(
        main_answer=message,
        confidence=0.0,
        confusion_tags=["model_output_failure"],
        missed_prerequisites=[],
        misconception_flags=[],
        evidence_slide_refs=slide_refs,
    )

