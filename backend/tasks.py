from __future__ import annotations

from backend.models import EvaluationTask, TaskType


DEFAULT_TASKS = [
    EvaluationTask(
        task_type=TaskType.explain_back,
        instruction="Read the assigned slide content and explain it back in your own words as a student.",
        question_set=[
            "What is the main idea of this content?",
            "How would you explain it simply?",
            "Which part are you least sure about?",
        ],
        output_format_hint=(
            "Return main_answer, confusion_tags, missed_prerequisites, misconception_flags, "
            "evidence_slide_refs"
        ),
    ),
    EvaluationTask(
        task_type=TaskType.short_qa,
        instruction="Answer short concept-check questions based on the assigned slide content.",
        question_set=[
            "What does the key term mean?",
            "What is the difference between concept A and concept B?",
            "What prior knowledge is needed to answer this correctly?",
        ],
        output_format_hint=(
            "Return main_answer, confidence, confusion_tags, missed_prerequisites, "
            "misconception_flags, evidence_slide_refs"
        ),
    ),
    EvaluationTask(
        task_type=TaskType.confusion_report,
        instruction="Report what is confusing, skipped, or too fast in the assigned slide content.",
        question_set=[
            "Which part is hard to understand?",
            "Where does the explanation jump too quickly?",
            "What would you want the teacher to clarify?",
        ],
        output_format_hint="Return main_answer, confusion_tags, missed_prerequisites, evidence_slide_refs",
    ),
    EvaluationTask(
        task_type=TaskType.coverage_check,
        instruction="Check whether the content misses important details, caveats, or boundary conditions.",
        question_set=[
            "What important point is not fully covered?",
            "What assumption or boundary is missing?",
            "What should be added to make this explanation more complete?",
        ],
        output_format_hint="Return main_answer, misconception_flags, evidence_slide_refs",
    ),
]

TASK_MAP = {task.task_type: task for task in DEFAULT_TASKS}

