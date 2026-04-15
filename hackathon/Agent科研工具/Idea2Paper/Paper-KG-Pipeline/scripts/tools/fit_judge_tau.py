#!/usr/bin/env python3
"""
Fit judge tau for blind reviewer calibration.
Uses nodes_paper.json to sample paper pairs, calls LLM for blind judgement,
and fits tau via NLL grid search.
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from idea2paper.infra.dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=False)
except Exception:
    pass

from idea2paper.config import OUTPUT_DIR, LLM_MODEL
from idea2paper.infra.llm import call_llm, parse_json_from_llm
from idea2paper.application.review.cards import build_paper_card, CARD_VERSION
from idea2paper.application.review.rubric import get_rubric, RUBRIC_VERSION


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _file_hash(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def nll_loss(deltas: List[float], ys: List[float], weights: List[float], tau: float) -> float:
    eps = 1e-9
    total = 0.0
    for delta, y, w in zip(deltas, ys, weights):
        p = sigmoid(delta / tau)
        p = max(eps, min(1 - eps, p))
        total += w * (-(y * math.log(p) + (1 - y) * math.log(1 - p)))
    return total


def _strength_weight(strength: str) -> float:
    if strength == "strong":
        return 3.0
    if strength == "medium":
        return 2.0
    return 1.0


def build_pair_prompt(role: str, card_a: Dict, card_b: Dict) -> str:
    rubric = get_rubric(role)
    def fmt(card):
        lines = []
        for key in ["problem", "method", "contrib"]:
            val = card.get(key, "")
            if val:
                lines.append(f"- {key}: {val}")
        return "\n".join(lines) if lines else "- (empty)"

    return f"""
You are a strict reviewer focused on **{role}**.
You MUST NOT output any numeric score, paper title, author, link, paper_id, or any real-world identifiers.
Compare Paper A vs Paper B using the rubric.

Rubric ({role}):
{rubric}

Paper A:
{fmt(card_a)}

Paper B:
{fmt(card_b)}

Task:
Output judgement of Paper A relative to Paper B:
- judgement: better | tie | worse
- strength: weak | medium | strong
- rationale: <= 25 words, only use card content, no identifiers.
Do NOT treat missing/shorter text as evidence of lower quality; if evidence is insufficient, prefer tie.

Return JSON ONLY:
{{
  "rubric_version": "{RUBRIC_VERSION}",
  "judgement": "better|tie|worse",
  "strength": "weak|medium|strong",
  "rationale": "..."
}}
"""


def parse_judge_response(resp: str) -> Tuple[str, str]:
    result = parse_json_from_llm(resp)
    if not isinstance(result, dict):
        return "", ""
    judgement = result.get("judgement", "")
    strength = result.get("strength", "")
    if judgement not in ("better", "tie", "worse"):
        return "", ""
    if strength not in ("weak", "medium", "strong"):
        return "", ""
    return judgement, strength


def sample_pairs(papers: List[Dict], target_per_bin: int, same_pattern_ratio: float, seed: int) -> List[Tuple[Dict, Dict]]:
    random.seed(seed)
    bins = {
        "near_0": (0.0, 0.25),
        "near_0_5": (0.25, 0.75),
        "near_1": (0.75, 1.5),
        "near_2": (1.5, 3.0),
    }
    picked = {k: [] for k in bins}
    papers_by_pattern: Dict[str, List[Dict]] = {}
    for p in papers:
        pid = p.get("pattern_id")
        if pid:
            papers_by_pattern.setdefault(pid, []).append(p)

    max_attempts = target_per_bin * 50
    attempts = 0
    while attempts < max_attempts and any(len(v) < target_per_bin for v in picked.values()):
        attempts += 1
        if random.random() < same_pattern_ratio and papers_by_pattern:
            pattern_id = random.choice(list(papers_by_pattern.keys()))
            plist = papers_by_pattern.get(pattern_id, [])
            if len(plist) < 2:
                continue
            a, b = random.sample(plist, 2)
        else:
            a, b = random.sample(papers, 2)
        delta = abs(a["score10"] - b["score10"])
        for name, (lo, hi) in bins.items():
            if lo <= delta < hi and len(picked[name]) < target_per_bin:
                picked[name].append((a, b))
                break
    pairs = []
    for group in picked.values():
        pairs.extend(group)
    random.shuffle(pairs)
    return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes_paper", type=str, default=str(OUTPUT_DIR / "nodes_paper.json"))
    parser.add_argument("--role", type=str, default="Methodology", choices=["Methodology", "Novelty", "Storyteller"])
    parser.add_argument("--pairs", type=int, default=2000)
    parser.add_argument("--same_pattern_ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=str(OUTPUT_DIR / "judge_pairs.jsonl"))
    parser.add_argument("--tau_out", type=str, default=str(OUTPUT_DIR / "judge_tau.json"))
    args = parser.parse_args()

    papers = json.loads(Path(args.nodes_paper).read_text(encoding="utf-8"))
    pool = []
    for p in papers:
        stats = p.get("review_stats", {}) or {}
        if not p.get("paper_id") or not p.get("pattern_id"):
            continue
        avg_score = float(stats.get("avg_score", 0.5))
        score10 = 1 + 9 * avg_score
        review_count = int(stats.get("review_count", 0))
        highest = float(stats.get("highest_score", avg_score))
        lowest = float(stats.get("lowest_score", avg_score))
        dispersion10 = 9 * (highest - lowest)
        weight = math.log(1 + review_count) / (1 + max(dispersion10, 0.0))
        pool.append({**p, "score10": score10, "weight": weight})

    per_bin = max(1, args.pairs // 4)
    pairs = sample_pairs(pool, per_bin, args.same_pattern_ratio, args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    deltas = []
    ys = []
    weights = []

    with out_path.open("w", encoding="utf-8") as f:
        for idx, (a, b) in enumerate(pairs):
            card_a = build_paper_card(a)
            card_b = build_paper_card(b)
            prompt = build_pair_prompt(args.role, card_a, card_b)
            resp = call_llm(prompt, temperature=0.0, max_tokens=4096, timeout=120)
            judgement, strength = parse_judge_response(resp)
            if not judgement:
                continue
            y = 1.0 if judgement == "better" else 0.0 if judgement == "worse" else 0.5
            strength_w = _strength_weight(strength)
            delta = a["score10"] - b["score10"]
            w = (a["weight"] + b["weight"]) / 2.0 * strength_w
            deltas.append(delta)
            ys.append(y)
            weights.append(w)
            f.write(json.dumps({
                "pair_id": idx,
                "paper_a": a.get("paper_id"),
                "paper_b": b.get("paper_id"),
                "delta": delta,
                "y": y,
                "strength": strength,
                "weight": w,
                "role": args.role,
                "rubric_version": RUBRIC_VERSION,
                "card_version": CARD_VERSION,
            }, ensure_ascii=False) + "\n")

    tau_grid = [round(x, 2) for x in [i * 0.01 for i in range(10, 301)]]
    best_tau = None
    best_nll = None
    for tau in tau_grid:
        loss = nll_loss(deltas, ys, weights, tau)
        if best_nll is None or loss < best_nll:
            best_nll = loss
            best_tau = tau

    tau_out = Path(args.tau_out)
    tau_out.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if tau_out.exists():
        try:
            existing = json.loads(tau_out.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    key = f"tau_{args.role.lower()}"
    existing[key] = best_tau
    existing["rubric_version"] = RUBRIC_VERSION
    existing["card_version"] = CARD_VERSION
    existing["judge_model"] = LLM_MODEL
    existing["nodes_paper_hash"] = _file_hash(Path(args.nodes_paper)) if Path(args.nodes_paper).exists() else None
    existing["created_at"] = datetime.now(timezone.utc).isoformat()
    existing["pairs_used"] = len(deltas)
    tau_out.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved pairs: {out_path}")
    print(f"Fitted tau ({args.role}): {best_tau} (NLL={best_nll:.4f})")
    print(f"Updated tau file: {tau_out}")


if __name__ == "__main__":
    main()
