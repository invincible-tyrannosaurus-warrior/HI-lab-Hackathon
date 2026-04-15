from __future__ import annotations

import math
from typing import Dict, List, Tuple


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _nll(y: float, p: float) -> float:
    eps = 1e-9
    p = max(eps, min(1 - eps, p))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _strength_weight(strength: str) -> float:
    if strength == "strong":
        return 3.0
    if strength == "medium":
        return 2.0
    return 1.0


def infer_score_from_comparisons(
    anchors: List[Dict],
    comparisons: List[Dict],
    tau: float,
    grid_step: float = 0.01,
) -> Tuple[float, Dict]:
    if tau is None or tau <= 0:
        tau = 1.0

    comp_map = {c.get("anchor_id"): c for c in comparisons if c.get("anchor_id")}
    ys: List[float] = []
    weights: List[float] = []
    scores: List[float] = []
    strength_vals: List[float] = []

    for anchor in anchors:
        anchor_id = anchor.get("anchor_id")
        comp = comp_map.get(anchor_id, {"judgement": "tie", "strength": "weak"})
        judgement = comp.get("judgement", "tie")
        strength = comp.get("strength", "weak")
        if judgement == "better":
            y = 1.0
        elif judgement == "worse":
            y = 0.0
        else:
            y = 0.5
        strength_w = _strength_weight(strength)
        anchor_weight = float(anchor.get("weight", 1.0))
        ys.append(y)
        weights.append(anchor_weight * strength_w)
        scores.append(float(anchor.get("score10", 5.0)))
        strength_vals.append(strength_w)

    best_s = 5.0
    best_loss = None
    s = 1.0
    losses = []
    grid = []
    while s <= 10.0 + 1e-9:
        loss = 0.0
        for y, w, score in zip(ys, weights, scores):
            p = _sigmoid((s - score) / tau)
            loss += w * _nll(y, p)
        losses.append(loss)
        grid.append(s)
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best_s = s
        s += grid_step

    ci_low = None
    ci_high = None
    if best_loss is not None and losses:
        threshold = best_loss + 1.92  # ~95% CI for 1 parameter
        within = [g for g, l in zip(grid, losses) if l <= threshold]
        if within:
            ci_low = min(within)
            ci_high = max(within)

    monotonic_violations = 0
    sorted_pairs = sorted(zip(scores, ys), key=lambda x: x[0])
    prev_y = None
    for score, y in sorted_pairs:
        if prev_y is not None and y > prev_y + 0.1:
            monotonic_violations += 1
        prev_y = y

    avg_strength = sum(strength_vals) / len(strength_vals) if strength_vals else 1.0

    detail = {
        "loss": best_loss if best_loss is not None else 0.0,
        "avg_strength": avg_strength,
        "monotonic_violations": monotonic_violations,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }
    return best_s, detail
