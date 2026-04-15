from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from idea2paper.config import PipelineConfig
from idea2paper.infra.run_context import get_logger

from .blind_judge import BlindJudge
from .cards import build_paper_card, build_story_card, CARD_VERSION
from .coach import CoachReviewer
from .review_index import ReviewIndex
from .rubric import RUBRIC_VERSION
from .score_inference import infer_score_from_comparisons


def _safe_mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


ROLE_TAU_KEYS = {
    "Methodology": "tau_methodology",
    "Novelty": "tau_novelty",
    "Storyteller": "tau_storyteller",
}


class MultiAgentCritic:
    """Blind, calibrated multi-agent critic with deterministic score inference."""

    def __init__(self, review_index: Optional[ReviewIndex] = None):
        self.review_index = review_index
        self.reviewers = [
            {"name": "Reviewer A", "role": "Methodology", "focus": "技术合理性"},
            {"name": "Reviewer B", "role": "Novelty", "focus": "创新性"},
            {"name": "Reviewer C", "role": "Storyteller", "focus": "叙事完整性"},
        ]
        self.judge = BlindJudge()
        self.coach = CoachReviewer()
        self.logger = get_logger()
        self._tau_config = self._load_tau_config(getattr(PipelineConfig, "JUDGE_TAU_PATH", None))

    def _log_event(self, event_type: str, payload: Dict):
        if self.logger:
            self.logger.log_event(event_type, payload)

    def _load_tau_config(self, path: Optional[Path]) -> Dict:
        if not path:
            return {}
        try:
            if Path(path).exists():
                return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {}

    def _get_tau(self, role: str) -> float:
        key = ROLE_TAU_KEYS.get(role, "")
        if key and key in self._tau_config:
            try:
                return float(self._tau_config[key])
            except Exception:
                pass
        if role == "Methodology":
            return float(getattr(PipelineConfig, "TAU_METHODOLOGY", 1.0))
        if role == "Novelty":
            return float(getattr(PipelineConfig, "TAU_NOVELTY", 1.0))
        if role == "Storyteller":
            return float(getattr(PipelineConfig, "TAU_STORYTELLER", 1.0))
        return float(getattr(PipelineConfig, "JUDGE_TAU_DEFAULT", 1.0))

    def _prepare_anchors(self, anchor_summaries: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        anchors = []
        cards = []
        seen = set()
        for idx, summary in enumerate(anchor_summaries):
            paper_id = summary.get("paper_id")
            if not paper_id or not self.review_index:
                continue
            if paper_id in seen:
                continue
            seen.add(paper_id)
            paper_node = self.review_index.get_paper_node(paper_id)
            if not paper_node:
                continue
            review_summary = self.review_index.get_review_summary(paper_id)
            card = build_paper_card(paper_node, review_summary)
            anchor_id = f"A{len(anchors) + 1}"
            anchors.append({
                "anchor_id": anchor_id,
                "paper_id": paper_id,
                "score10": summary.get("score10", 5.0),
                "weight": summary.get("weight", 1.0),
            })
            cards.append(card)
        return anchors, cards

    def _compute_pass_decision(self, avg_score: float, role_scores: Dict[str, float], pattern_id: str) -> Tuple[bool, Dict]:
        mode = getattr(PipelineConfig, "PASS_MODE", "two_of_three_q75_and_avg_ge_q50")
        min_papers = getattr(PipelineConfig, "PASS_MIN_PATTERN_PAPERS", 20)
        fallback = getattr(PipelineConfig, "PASS_FALLBACK", "global")

        used_distribution = "fixed"
        pattern_stats_n = 0
        q50 = None
        q75 = None

        if self.review_index and pattern_id:
            stats = self.review_index.get_pattern_quantiles(pattern_id, [0.5, 0.75])
            pattern_stats_n = int(stats.get("n", 0) or 0)
            if pattern_stats_n >= min_papers and stats.get("q50") is not None and stats.get("q75") is not None:
                q50 = float(stats.get("q50"))
                q75 = float(stats.get("q75"))
                used_distribution = "pattern"
            else:
                if fallback == "global":
                    gstats = self.review_index.get_global_quantiles([0.5, 0.75])
                    if gstats.get("q50") is not None and gstats.get("q75") is not None:
                        q50 = float(gstats.get("q50"))
                        q75 = float(gstats.get("q75"))
                        used_distribution = "global"
                if used_distribution == "fixed":
                    q50 = None
                    q75 = None

        roles = ["Methodology", "Novelty", "Storyteller"]
        roles_ge_q75 = {r: False for r in roles}
        count_ge_q75 = 0
        avg_ge_q50 = None

        passed = False
        if mode == "two_of_three_q75_and_avg_ge_q50" and q50 is not None and q75 is not None:
            roles_ge_q75 = {r: float(role_scores.get(r, 0.0)) >= q75 for r in roles}
            count_ge_q75 = sum(1 for v in roles_ge_q75.values() if v)
            avg_ge_q50 = avg_score >= q50
            passed = (count_ge_q75 >= 2) and avg_ge_q50
        else:
            passed = avg_score >= PipelineConfig.PASS_SCORE

        pass_audit = {
            "mode": mode if mode else "fixed",
            "used_distribution": used_distribution,
            "pattern_paper_count": pattern_stats_n,
            "q50": q50,
            "q75": q75,
            "count_roles_ge_q75": count_ge_q75,
            "roles_ge_q75": roles_ge_q75,
            "avg_ge_q50": avg_ge_q50,
            "avg_score": avg_score,
        }

        return passed, pass_audit

    def _diagnose_issue(self, reviews: List[Dict], scores: List[float]) -> Tuple[str, List[str]]:
        if not reviews or not scores:
            return "novelty", ["从novelty维度选择创新Pattern"]
        min_idx = scores.index(min(scores))
        worst_review = reviews[min_idx]
        role = worst_review.get("role", "")
        if role == "Novelty":
            return "novelty", ["从novelty维度选择创新Pattern", "注入长尾Pattern提升新颖性"]
        if role == "Methodology":
            return "stability", ["从stability维度选择稳健Pattern", "注入成熟方法增强鲁棒性"]
        if role == "Storyteller":
            return "domain_distance", ["从domain_distance维度选择跨域Pattern", "引入不同视角优化叙事"]
        return "novelty", ["从novelty维度选择创新Pattern"]

    def _blind_review_role(self, story_card: Dict, anchors: List[Dict], anchor_cards: List[Dict], role: str) -> Dict:
        comparisons = self.judge.judge(role, story_card, anchor_cards)["comparisons"]
        tau = self._get_tau(role)
        score, detail = infer_score_from_comparisons(
            anchors=anchors,
            comparisons=comparisons,
            tau=tau,
            grid_step=getattr(PipelineConfig, "GRID_STEP", 0.01),
        )
        feedback = (
            f"Blind comparisons vs {len(anchors)} anchors. "
            f"Loss={detail.get('loss', 0.0):.4f}, "
            f"AvgStrength={detail.get('avg_strength', 1.0):.2f}."
        )
        return {
            "score": score,
            "feedback": feedback,
            "detail": {
                "comparisons": comparisons,
                "loss": detail.get("loss"),
                "avg_strength": detail.get("avg_strength"),
                "monotonic_violations": detail.get("monotonic_violations"),
                "ci_low": detail.get("ci_low"),
                "ci_high": detail.get("ci_high"),
                "tau": tau,
            },
        }

    def review(self, story: Dict, context: Optional[Dict] = None) -> Dict:
        print("\n" + "=" * 80)
        print("🔍 Phase 3: Multi-Agent Critic (Blind + Calibrated)")
        print("=" * 80)

        context = context or {}
        pattern_id = context.get("pattern_id", "")
        pattern_info = context.get("pattern_info", {}) or {}
        anchors_input = context.get("anchors", []) or []

        if not anchors_input and pattern_id and self.review_index:
            print(f"  📌 选择初始 anchors：pattern_id={pattern_id}")
            anchors_input = self.review_index.select_initial_anchors(
                pattern_id,
                pattern_info,
                max_initial=getattr(PipelineConfig, "ANCHOR_MAX_INITIAL", 11),
                quantiles=getattr(PipelineConfig, "ANCHOR_QUANTILES", None),
                max_exemplars=getattr(PipelineConfig, "ANCHOR_MAX_EXEMPLARS", 2),
            )
        if anchors_input:
            print(f"  📎 初始 anchors 数量（summaries）：{len(anchors_input)}")

        if not anchors_input:
            reviews = []
            scores = []
            for reviewer in self.reviewers:
                reviews.append({
                    "reviewer": reviewer["name"],
                    "role": reviewer["role"],
                    "score": 5.0,
                    "feedback": "No anchors available; defaulted to neutral score.",
                })
                scores.append(5.0)
            avg_score = _safe_mean(scores)
            main_issue, suggestions = self._diagnose_issue(reviews, scores)
            return {
                "pass": avg_score >= PipelineConfig.PASS_SCORE,
                "avg_score": avg_score,
                "reviews": reviews,
                "main_issue": main_issue,
                "suggestions": suggestions,
                "audit": {
                    "pattern_id": pattern_id,
                    "anchors": [],
                    "role_details": {},
                    "rubric_version": RUBRIC_VERSION,
                    "card_version": CARD_VERSION,
                },
            }

        anchors, anchor_cards = self._prepare_anchors(anchors_input)
        if not anchors:
            reviews = []
            scores = []
            for reviewer in self.reviewers:
                reviews.append({
                    "reviewer": reviewer["name"],
                    "role": reviewer["role"],
                    "score": 5.0,
                    "feedback": "Anchors unavailable after card build; defaulted to neutral score.",
                })
                scores.append(5.0)
            avg_score = _safe_mean(scores)
            main_issue, suggestions = self._diagnose_issue(reviews, scores)
            return {
                "pass": avg_score >= PipelineConfig.PASS_SCORE,
                "avg_score": avg_score,
                "reviews": reviews,
                "main_issue": main_issue,
                "suggestions": suggestions,
                "audit": {
                    "pattern_id": pattern_id,
                    "anchors": [],
                    "role_details": {},
                    "rubric_version": RUBRIC_VERSION,
                    "card_version": CARD_VERSION,
                },
            }
        story_card = build_story_card(story)

        def _run_round(current_anchors, current_cards):
            reviews = []
            scores = []
            role_details = {}
            for reviewer in self.reviewers:
                role = reviewer["role"]
                print(f"  ⏳ 盲测对比中：role={role} | anchors={len(current_anchors)}")
                result = self._blind_review_role(story_card, current_anchors, current_cards, role)
                detail = result.get("detail", {}) or {}
                try:
                    print(
                        f"    ✅ 完成：role={role} | S={float(result['score']):.2f} | "
                        f"loss={float(detail.get('loss', 0.0)):.4f} | "
                        f"avg_strength={float(detail.get('avg_strength', 0.0)):.2f} | "
                        f"tau={float(detail.get('tau', 1.0)):.2f}"
                    )
                except Exception:
                    print(f"    ✅ 完成：role={role}")
                reviews.append({
                    "reviewer": reviewer["name"],
                    "role": role,
                    "score": result["score"],
                    "feedback": result["feedback"],
                })
                scores.append(result["score"])
                role_details[role] = result["detail"]
            return reviews, scores, role_details

        print(f"  🧩 构建 Blind Cards：story_card+anchor_cards={len(anchor_cards)}")
        reviews1, scores1, role_details1 = _run_round(anchors, anchor_cards)
        densify_enabled = getattr(PipelineConfig, "ANCHOR_DENSIFY_ENABLE", True)
        densify_needed = any(
            (detail.get("loss", 0.0) > getattr(PipelineConfig, "DENSIFY_LOSS_THRESHOLD", 0.05))
            or (detail.get("monotonic_violations", 0) >= 1)
            or (detail.get("avg_strength", 1.0) < getattr(PipelineConfig, "DENSIFY_MIN_AVG_CONF", 0.35))
            for detail in role_details1.values()
        )

        anchors_rounds = [anchors]
        if densify_enabled and densify_needed and pattern_id and self.review_index:
            print("  🔁 densify 触发：补充 anchors 并进行第二轮盲测（用于提高稳定性/一致性）")
            s_hint = _safe_mean(scores1) if scores1 else 5.0
            bucket_center = round(s_hint * 2) / 2.0
            bucket_size = getattr(PipelineConfig, "ANCHOR_BUCKET_SIZE", 1.0)
            bucket_count = getattr(PipelineConfig, "ANCHOR_BUCKET_COUNT", 3)
            print(
                f"    🎯 densify bucket：center≈{bucket_center:.2f} | size={float(bucket_size):.2f} | count={int(bucket_count)}"
            )
            bucket_anchors = self.review_index.select_bucket_anchors(
                pattern_id=pattern_id,
                bucket_center=bucket_center,
                bucket_size=bucket_size,
                count=bucket_count,
            )
            extra = []
            for a in bucket_anchors:
                if a["paper_id"] not in {x["paper_id"] for x in anchors}:
                    extra.append(a)
            if extra:
                anchors_extended = anchors_input + extra
                anchors, anchor_cards = self._prepare_anchors(anchors_extended)
                print(f"    ➕ densify 新增 anchors：{len(extra)}（总 anchors={len(anchors)}）")
                anchors_rounds.append(extra)
                reviews2, scores2, role_details2 = _run_round(anchors, anchor_cards)
            else:
                print("    ℹ️ densify 未找到可新增 anchors，跳过第二轮")
                reviews2, scores2, role_details2 = reviews1, scores1, role_details1
        else:
            reviews2, scores2, role_details2 = reviews1, scores1, role_details1

        avg_score = _safe_mean(scores2)
        role_scores = {r["role"]: r["score"] for r in reviews2}
        passed, pass_audit = self._compute_pass_decision(avg_score, role_scores, pattern_id)
        main_issue, suggestions = self._diagnose_issue(reviews2, scores2)

        print(f"  🧾 评分汇总：avg_score={avg_score:.2f} | pass={passed} | main_issue={main_issue}")

        print("  🛠️  Coach Layer：生成字段级可执行改稿建议…")
        coach_result = self.coach.review(story, role_scores, main_issue)
        priority = coach_result.get("priority", [])
        if priority:
            print(f"    ✅ Coach 完成：priority={', '.join(priority[:6])}")
        else:
            print("    ✅ Coach 完成")

        if priority:
            for review in reviews2:
                review["feedback"] = review["feedback"] + f" CoachPriority: {', '.join(priority[:3])}."

        audit = {
            "pattern_id": pattern_id,
            "anchors": anchors,
            "anchors_rounds": anchors_rounds,
            "role_details": role_details2,
            "pass": pass_audit,
            "rubric_version": RUBRIC_VERSION,
            "card_version": CARD_VERSION,
        }

        self._log_event("pass_threshold_computed", {
            "pattern_id": pattern_id,
            "used_distribution": pass_audit.get("used_distribution"),
            "q50": pass_audit.get("q50"),
            "q75": pass_audit.get("q75"),
            "count_roles_ge_q75": pass_audit.get("count_roles_ge_q75"),
            "avg_score": avg_score,
            "passed": passed,
        })

        return {
            "pass": passed,
            "avg_score": avg_score,
            "reviews": reviews2,
            "main_issue": main_issue,
            "suggestions": suggestions,
            "audit": audit,
            "field_feedback": coach_result.get("field_feedback", {}),
            "suggested_edits": coach_result.get("suggested_edits", []),
            "priority": coach_result.get("priority", []),
            "review_coach": coach_result,
        }
