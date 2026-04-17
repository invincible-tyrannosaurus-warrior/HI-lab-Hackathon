from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any
import uuid


ACTION_PRIORITY = {
    "add_prerequisite_slide": 95,
    "rewrite_explanation": 90,
    "add_misconception_warning": 85,
    "add_example": 80,
    "split_dense_slide": 70,
    "regenerate_deck_section": 65,
    "mark_for_kb_review": 60,
}


@dataclass
class SignalInput:
    tested_deck_id: str
    weak_topics: List[str]
    repeated_confusion_points: List[str]
    misconception_clusters: List[str]
    missing_prerequisite_patterns: List[str]
    evidence_refs: List[str]
    recommended_revision_targets: List[str] = field(default_factory=list)
    slide_refs: List[str] = field(default_factory=list)
    source_knowledge_ids: List[str] = field(default_factory=list)


@dataclass
class Issue:
    issue_id: str
    issue_type: str
    topic: str
    severity: str
    score: int
    affected_slide_refs: List[str]
    rationale: str
    evidence_refs: List[str]


@dataclass
class Recommendation:
    recommendation_id: str
    action: str
    priority: str
    score: int
    target_deck_id: str
    target_slide_refs: List[str]
    target_knowledge_ids: List[str]
    rationale: str
    evidence_refs: List[str]
    source_issue_ids: List[str]


@dataclass
class ProposalCandidate:
    proposal_candidate_id: str
    target_deck_id: str
    target_knowledge_ids: List[str]
    recommended_action: str
    rationale: str
    evidence_refs: List[str]
    suggested_priority: str
    based_on_issue_ids: List[str]


class AnalyticsEngine:
    def analyze(self, signal: SignalInput) -> Dict[str, Any]:
        issues = self._build_issues(signal)
        recommendations = self._build_recommendations(signal, issues)
        proposal_candidates = self._build_proposals(signal, recommendations)

        return {
            "deck_id": signal.tested_deck_id,
            "issues": [asdict(x) for x in issues],
            "recommendations": [asdict(x) for x in recommendations],
            "proposal_candidates": [asdict(x) for x in proposal_candidates],
        }

    def _build_issues(self, signal: SignalInput) -> List[Issue]:
        issues: List[Issue] = []

        for topic in signal.weak_topics:
            score = 60
            if topic and self._topic_related_confusions(topic, signal.repeated_confusion_points):
                score += 10
            if topic and self._topic_related_misconceptions(topic, signal.misconception_clusters):
                score += 10
            if signal.missing_prerequisite_patterns:
                score += 5

            issues.append(
                Issue(
                    issue_id=self._new_id("issue"),
                    issue_type="weak_topic",
                    topic=topic,
                    severity=self._severity_from_score(score),
                    score=score,
                    affected_slide_refs=signal.slide_refs,
                    rationale=f"Topic '{topic}' appears in weak_topics and is repeatedly problematic.",
                    evidence_refs=signal.evidence_refs,
                )
            )

        for confusion in signal.repeated_confusion_points:
            score = 75
            issues.append(
                Issue(
                    issue_id=self._new_id("issue"),
                    issue_type="confusion_point",
                    topic=self._guess_topic(confusion, signal.weak_topics),
                    severity=self._severity_from_score(score),
                    score=score,
                    affected_slide_refs=signal.slide_refs,
                    rationale=f"Students repeatedly showed confusion about: {confusion}",
                    evidence_refs=signal.evidence_refs,
                )
            )

        for misconception in signal.misconception_clusters:
            score = 80
            issues.append(
                Issue(
                    issue_id=self._new_id("issue"),
                    issue_type="misconception",
                    topic=self._guess_topic(misconception, signal.weak_topics),
                    severity=self._severity_from_score(score),
                    score=score,
                    affected_slide_refs=signal.slide_refs,
                    rationale=f"A recurring misconception was found: {misconception}",
                    evidence_refs=signal.evidence_refs,
                )
            )

        for prereq in signal.missing_prerequisite_patterns:
            score = 88
            issues.append(
                Issue(
                    issue_id=self._new_id("issue"),
                    issue_type="missing_prerequisite",
                    topic=self._guess_topic(prereq, signal.weak_topics),
                    severity=self._severity_from_score(score),
                    score=score,
                    affected_slide_refs=signal.slide_refs,
                    rationale=f"Students are likely missing prerequisite knowledge: {prereq}",
                    evidence_refs=signal.evidence_refs,
                )
            )

        return sorted(issues, key=lambda x: x.score, reverse=True)

    def _build_recommendations(
        self, signal: SignalInput, issues: List[Issue]
    ) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        for issue in issues:
            action = self._map_issue_to_action(issue)
            score = min(100, issue.score + (ACTION_PRIORITY.get(action, 50) // 10))

            recommendations.append(
                Recommendation(
                    recommendation_id=self._new_id("rec"),
                    action=action,
                    priority=self._priority_from_score(score),
                    score=score,
                    target_deck_id=signal.tested_deck_id,
                    target_slide_refs=issue.affected_slide_refs,
                    target_knowledge_ids=signal.source_knowledge_ids,
                    rationale=issue.rationale,
                    evidence_refs=issue.evidence_refs,
                    source_issue_ids=[issue.issue_id],
                )
            )

        # 如果问题密度高，再补一个整段重生成建议
        if len(issues) >= 4:
            recommendations.append(
                Recommendation(
                    recommendation_id=self._new_id("rec"),
                    action="regenerate_deck_section",
                    priority="medium",
                    score=68,
                    target_deck_id=signal.tested_deck_id,
                    target_slide_refs=signal.slide_refs,
                    target_knowledge_ids=signal.source_knowledge_ids,
                    rationale="Multiple issue types were detected across the same deck section.",
                    evidence_refs=signal.evidence_refs,
                    source_issue_ids=[x.issue_id for x in issues[:3]],
                )
            )

        # 去重：同类 action 只保留分数最高的一条
        best_by_action: Dict[str, Recommendation] = {}
        for rec in recommendations:
            if rec.action not in best_by_action or rec.score > best_by_action[rec.action].score:
                best_by_action[rec.action] = rec

        return sorted(best_by_action.values(), key=lambda x: x.score, reverse=True)

    def _build_proposals(
        self, signal: SignalInput, recommendations: List[Recommendation]
    ) -> List[ProposalCandidate]:
        proposals: List[ProposalCandidate] = []

        for rec in recommendations:
            if rec.priority in {"high", "medium"}:
                proposals.append(
                    ProposalCandidate(
                        proposal_candidate_id=self._new_id("pc"),
                        target_deck_id=signal.tested_deck_id,
                        target_knowledge_ids=rec.target_knowledge_ids,
                        recommended_action=rec.action,
                        rationale=rec.rationale,
                        evidence_refs=rec.evidence_refs,
                        suggested_priority=rec.priority,
                        based_on_issue_ids=rec.source_issue_ids,
                    )
                )

        return proposals

    def _map_issue_to_action(self, issue: Issue) -> str:
        if issue.issue_type == "missing_prerequisite":
            return "add_prerequisite_slide"
        if issue.issue_type == "misconception":
            return "add_misconception_warning"
        if issue.issue_type == "confusion_point":
            if "difference" in issue.rationale.lower() or "why" in issue.rationale.lower():
                return "rewrite_explanation"
            return "add_example"
        if issue.issue_type == "weak_topic":
            if issue.score >= 75:
                return "rewrite_explanation"
            return "add_example"
        return "mark_for_kb_review"

    def _severity_from_score(self, score: int) -> str:
        if score >= 85:
            return "high"
        if score >= 70:
            return "medium"
        return "low"

    def _priority_from_score(self, score: int) -> str:
        if score >= 85:
            return "high"
        if score >= 70:
            return "medium"
        return "low"

    def _guess_topic(self, text: str, weak_topics: List[str]) -> str:
        text_lower = text.lower()
        for topic in weak_topics:
            if topic.lower() in text_lower:
                return topic
        return weak_topics[0] if weak_topics else "unknown"

    def _topic_related_confusions(self, topic: str, confusions: List[str]) -> bool:
        topic_lower = topic.lower()
        return any(topic_lower in c.lower() for c in confusions)

    def _topic_related_misconceptions(self, topic: str, misconceptions: List[str]) -> bool:
        topic_lower = topic.lower()
        return any(topic_lower in m.lower() for m in misconceptions)

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"


if __name__ == "__main__":
    sample_input = SignalInput(
        tested_deck_id="deck_ml_week3_v1",
        weak_topics=["entropy intuition", "information gain"],
        repeated_confusion_points=[
            "why lower entropy is better",
            "difference between impurity and error",
        ],
        misconception_clusters=[
            "entropy equals randomness only",
        ],
        missing_prerequisite_patterns=[
            "log intuition missing",
        ],
        evidence_refs=["run_001", "run_002", "run_005"],
        slide_refs=["slide_03", "slide_04"],
        source_knowledge_ids=["kb_014", "kb_019"],
    )

    engine = AnalyticsEngine()
    result = engine.analyze(sample_input)

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
