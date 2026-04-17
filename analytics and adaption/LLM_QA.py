ISSUE_TAXONOMY = [
    "missing_prerequisite",
    "concept_confusion",
    "terminology_confusion",
    "theory_practice_gap",
    "insufficient_example",
    "misconception",
    "overly_dense_content",
    "weak_problem_decomposition",
    "weak_mathematical_foundation",
    "assessment_alignment_issue",
    "pace_too_fast",
    "abstraction_too_high",
]

ACTION_TAXONOMY = [
    "add_prerequisite_slide",
    "add_bridging_example",
    "add_worked_example",
    "rewrite_explanation",
    "simplify_terminology",
    "split_dense_slide",
    "add_visual_diagram",
    "add_misconception_warning",
    "add_step_by_step_trace",
    "add_formative_quiz",
    "resequence_topic_order",
    "slow_down_pacing",
    "regenerate_section",
    "mark_for_human_review",
]

ISSUE_TO_ACTIONS = {
    "missing_prerequisite": [
        "add_prerequisite_slide",
        "add_bridging_example",
        "resequence_topic_order",
    ],
    "concept_confusion": [
        "rewrite_explanation",
        "add_worked_example",
        "add_step_by_step_trace",
    ],
    "misconception": [
        "add_misconception_warning",
        "rewrite_explanation",
        "add_visual_diagram",
    ],
    "weak_mathematical_foundation": [
        "add_prerequisite_slide",
        "add_bridging_example",
        "add_visual_diagram",
    ],
    "theory_practice_gap": [
        "add_worked_example",
        "add_formative_quiz",
        "add_step_by_step_trace",
    ]
}


def build_issue_candidates(signal_summary: dict):
    candidates = []

    if signal_summary.get("missing_prerequisite_patterns"):
        candidates.append("missing_prerequisite")

    if signal_summary.get("misconception_clusters"):
        candidates.append("misconception")

    if signal_summary.get("repeated_confusion_points"):
        candidates.append("concept_confusion")

    text_blob = " ".join(signal_summary.get("repeated_confusion_points", [])).lower()
    if any(k in text_blob for k in ["trace", "step", "justify", "derive"]):
        candidates.append("weak_problem_decomposition")

    if any(k in text_blob for k in ["math", "probability", "log", "proof", "complexity"]):
        candidates.append("weak_mathematical_foundation")

    return sorted(set(candidates))


def build_action_candidates(issue_candidates: list):
    actions = []
    for issue in issue_candidates:
        actions.extend(ISSUE_TO_ACTIONS.get(issue, []))
    return sorted(set(actions))
