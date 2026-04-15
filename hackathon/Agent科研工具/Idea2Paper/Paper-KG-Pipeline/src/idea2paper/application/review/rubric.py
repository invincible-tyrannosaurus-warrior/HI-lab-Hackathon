RUBRIC_VERSION = "rubric_v1"

RUBRICS = {
    "Methodology": (
        "Evaluate technical soundness: clarity of method, feasibility, "
        "experimental rigor, and reproducibility. Reward well-justified "
        "design choices and complete evaluation plans; penalize vague "
        "or brittle methods."
    ),
    "Novelty": (
        "Evaluate originality: novelty of the problem framing, method "
        "innovation beyond common combinations, and the uniqueness of "
        "the contribution. Penalize routine stacking or obvious extensions."
    ),
    "Storyteller": (
        "Evaluate narrative quality: motivation→gap→method→experiment→conclusion "
        "coherence, clarity of claims, and completeness. Penalize gaps, "
        "hand-wavy claims, or missing experimental closure."
    ),
    "Overall": (
        "Evaluate overall research quality across method soundness, novelty, "
        "and narrative completeness."
    )
}


def get_rubric(role: str) -> str:
    return RUBRICS.get(role, RUBRICS["Overall"])
