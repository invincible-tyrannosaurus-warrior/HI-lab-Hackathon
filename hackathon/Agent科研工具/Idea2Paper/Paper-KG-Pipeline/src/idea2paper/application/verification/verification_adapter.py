from typing import Dict, List, Optional


def _pick_similarity(candidate: Dict, metric: str) -> float:
    if metric == "cosine":
        return float(candidate.get("cosine", 0.0) or 0.0)
    if metric == "keyword_overlap":
        return float(candidate.get("keyword_overlap", 0.0) or 0.0)
    return 0.0


def verification_from_novelty_report(
    novelty_report: Optional[Dict],
    collision_threshold: float,
) -> Dict:
    """
    Normalize novelty_report into verification_result.
    """
    result = {
        "pass": True,
        "collision_detected": False,
        "similar_papers": [],
        "max_similarity": 0.0,
        "source": "novelty_report",
        "metric": "unknown",
    }

    if not novelty_report:
        return result

    embedding_available = bool(novelty_report.get("embedding_available", False))
    metric = "cosine" if embedding_available else "keyword_overlap"
    candidates = novelty_report.get("candidates") or []
    top_candidates = candidates[:3]

    max_similarity = 0.0
    if candidates:
        max_similarity = max(_pick_similarity(c, metric) for c in candidates)

    similar_papers: List[Dict] = []
    for c in top_candidates:
        similar_papers.append({
            "paper_id": c.get("paper_id", ""),
            "title": c.get("title", ""),
            "pattern_id": c.get("pattern_id", ""),
            "domain": c.get("domain", ""),
            "similarity": _pick_similarity(c, metric),
        })

    collision_detected = max_similarity > collision_threshold

    result.update({
        "pass": not collision_detected,
        "collision_detected": collision_detected,
        "similar_papers": similar_papers,
        "max_similarity": max_similarity,
        "metric": metric,
    })
    return result
