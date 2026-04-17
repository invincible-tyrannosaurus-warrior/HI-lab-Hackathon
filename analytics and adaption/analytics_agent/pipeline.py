"""
Analytics & Adaptation — 完整 Pipeline
合并了: schemas / prompts / LLM pipeline / rule-based fallback engine
支持: DashScope (阿里云) / OpenAI / Gemini 自动检测
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ╔══════════════════════════════════════════════════════════════╗
# ║  Part 1 — Taxonomy & Schemas                                ║
# ╚══════════════════════════════════════════════════════════════╝


class IssueType(str, Enum):
    CONFUSION = "confusion"
    MISCONCEPTION = "misconception"
    MISSING_PREREQUISITE = "missing_prerequisite"
    PACING_MISMATCH = "pacing_mismatch"
    EXPRESSION_UNCLEAR = "expression_unclear"
    CONCEPT_CONFUSION = "concept_confusion"
    WEAK_MATH_FOUNDATION = "weak_mathematical_foundation"
    THEORY_PRACTICE_GAP = "theory_practice_gap"


class ActionType(str, Enum):
    ADD_PREREQUISITE_SLIDE = "add_prerequisite_slide"
    ADD_EXAMPLE = "add_example"
    REWRITE_EXPLANATION = "rewrite_explanation"
    SPLIT_DENSE_SLIDE = "split_dense_slide"
    ADD_MISCONCEPTION_WARNING = "add_misconception_warning"
    MARK_FOR_KB_REVIEW = "mark_for_kb_review"
    REGENERATE_DECK_SECTION = "regenerate_deck_section"


ISSUE_TO_ACTIONS = {
    "missing_prerequisite":        ["add_prerequisite_slide", "add_example"],
    "misconception":               ["add_misconception_warning", "rewrite_explanation"],
    "confusion":                   ["add_example", "rewrite_explanation"],
    "concept_confusion":           ["rewrite_explanation", "add_example"],
    "weak_mathematical_foundation":["add_prerequisite_slide", "add_example"],
    "expression_unclear":          ["rewrite_explanation", "split_dense_slide"],
    "pacing_mismatch":             ["split_dense_slide", "rewrite_explanation"],
    "theory_practice_gap":         ["add_example", "regenerate_deck_section"],
}

ACTION_PRIORITY = {
    "add_prerequisite_slide":     95,
    "rewrite_explanation":        90,
    "add_misconception_warning":  85,
    "add_example":                80,
    "split_dense_slide":          70,
    "regenerate_deck_section":    65,
    "mark_for_kb_review":         60,
}


@dataclass
class SignalSummary:
    tested_deck_id: str
    weak_topics: list[str]
    repeated_confusion_points: list[str]
    misconception_clusters: list[str]
    missing_prerequisite_patterns: list[str]
    recommended_revision_targets: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class DeckMetadata:
    deck_id: str
    slide_refs: list[str]
    topic_scope: list[str]
    source_knowledge_ids: list[str]
    generation_version: str = "v1"


@dataclass
class KnowledgeEntry:
    knowledge_id: str
    topic_tags: list[str]
    pedagogical_role: str
    source_ref: str
    version_number: str = "1.0"


# ╔══════════════════════════════════════════════════════════════╗
# ║  Part 2 — Prompt Templates (inline, 不再需要 prompts/ 目录)  ║
# ╚══════════════════════════════════════════════════════════════╝

PROMPTS = {
    "step1_ingest": {
        "system": (
            "You are the Signal Ingestion step of the Analytics & Adaptation pipeline.\n"
            "Your job: validate and enrich a raw cohort-style signal summary from Student Agent Testing.\n\n"
            "Rules:\n"
            "- Check field completeness: weak_topics, confusion_points, misconception_clusters, missing_prerequisites must all be non-empty.\n"
            "- Cross-reference with deck metadata to attach affected slide_refs to each issue mention.\n"
            "- Tag each item with a preliminary issue_type from this taxonomy:\n"
            "  confusion | misconception | missing_prerequisite | pacing_mismatch | expression_unclear\n"
            "- Output a clean JSON object ready for downstream normalization."
        ),
        "user": (
            "## Signal Summary\n{signal_json}\n\n"
            "## Deck Metadata\n{deck_json}\n\n"
            "## Knowledge Entries\n{knowledge_json}\n\n"
            "Please ingest and validate the signal. For each issue mention, attach the most likely affected slide_refs and a preliminary issue_type tag.\n\n"
            "Return a JSON object with this structure:\n"
            '{{\n'
            '  "signal_id": "<generated>",\n'
            '  "deck_id": "<from signal>",\n'
            '  "status": "ingested",\n'
            '  "field_completeness": {{ "weak_topics": true/false, ... }},\n'
            '  "tagged_issues": [\n'
            '    {{\n'
            '      "raw_text": "<original text>",\n'
            '      "preliminary_issue_type": "<taxonomy value>",\n'
            '      "likely_affected_slides": ["slide_ref", ...],\n'
            '      "source_field": "weak_topics | confusion_points | misconception_clusters | missing_prerequisites"\n'
            '    }}\n'
            '  ]\n'
            '}}'
        ),
    },
    "step2_normalize": {
        "system": (
            "You are the Issue Normalization step of the Analytics & Adaptation pipeline.\n"
            "Your job: take the tagged issues from ingestion and normalize them into a canonical issue list.\n\n"
            "Rules:\n"
            "- Each issue gets a unique issue_id (format: ISS_001, ISS_002, ...).\n"
            "- Merge duplicates or near-duplicates that describe the same underlying problem.\n"
            "- Assign exactly ONE issue_type per issue from: confusion | misconception | missing_prerequisite | pacing_mismatch | expression_unclear\n"
            "- Identify the primary topic each issue belongs to.\n"
            "- Keep affected_slides from the ingestion step.\n"
            "- Write a concise one-line description for each."
        ),
        "user": (
            "## Tagged Issues from Ingestion\n{tagged_issues_json}\n\n"
            "Normalize these into a deduplicated, structured issue list.\n\n"
            "Return JSON:\n"
            '{{\n'
            '  "normalized_issues": [\n'
            '    {{\n'
            '      "issue_id": "ISS_001",\n'
            '      "issue_type": "<taxonomy>",\n'
            '      "topic": "<primary topic>",\n'
            '      "affected_slides": ["..."],\n'
            '      "description": "<one-line>",\n'
            '      "source_evidence": ["run_xxx", ...]\n'
            '    }}\n'
            '  ]\n'
            '}}'
        ),
    },
    "step3_cluster": {
        "system": (
            "You are the Issue Clustering step of the Analytics & Adaptation pipeline.\n"
            "Your job: group normalized issues by three dimensions — topic, slide, and concept.\n\n"
            "Rules:\n"
            "- Create clusters for each dimension where 2+ issues share the same attribute.\n"
            "- Each cluster gets a unique cluster_id (format: CLU_T_001 for topic, CLU_S_001 for slide, CLU_C_001 for concept).\n"
            "- Write a short summary explaining why these issues cluster together.\n"
            "- An issue can appear in multiple clusters across dimensions."
        ),
        "user": (
            "## Normalized Issues\n{normalized_issues_json}\n\n"
            "Group these issues into clusters along three dimensions: topic, slide, concept.\n\n"
            "Return JSON:\n"
            '{{\n'
            '  "issue_clusters": [\n'
            '    {{\n'
            '      "cluster_id": "CLU_T_001",\n'
            '      "dimension": "topic",\n'
            '      "label": "<cluster label>",\n'
            '      "issues": ["ISS_001", "ISS_002"],\n'
            '      "summary": "<why these cluster>"\n'
            '    }}\n'
            '  ]\n'
            '}}'
        ),
    },
    "step4_score": {
        "system": (
            "You are the Severity Scoring step of the Analytics & Adaptation pipeline.\n"
            "Your job: score and rank issues by severity.\n\n"
            "Scoring criteria (from the development spec):\n"
            "1. Multi-profile trigger: issues flagged by BOTH weak AND strong student profiles rank higher.\n"
            "2. Strong-student signal: if a strong student also struggles, severity increases.\n"
            "3. Learning-objective impact: issues directly blocking a core learning objective rank higher.\n"
            "4. Repetition: issues appearing across multiple runs or slides rank higher.\n\n"
            "Severity levels: critical | high | medium | low\n"
            "Score range: 0.0 to 1.0\n\n"
            "Rules:\n"
            "- Consider all four criteria holistically.\n"
            "- Output issues sorted by score descending.\n"
            '- Include a brief profile_coverage note (e.g., "all profiles", "weak + average", "weak only").'
        ),
        "user": (
            "## Normalized Issues\n{normalized_issues_json}\n\n"
            "## Issue Clusters\n{clusters_json}\n\n"
            "## Context\n"
            "- Deck topic scope: {topic_scope}\n"
            "- Total evidence runs: {evidence_count}\n\n"
            "Score each issue and rank them.\n\n"
            "Return JSON:\n"
            '{{\n'
            '  "ranked_issues": [\n'
            '    {{\n'
            '      "issue_id": "ISS_001",\n'
            '      "topic": "<topic>",\n'
            '      "issue_type": "<type>",\n'
            '      "severity": "critical|high|medium|low",\n'
            '      "score": 0.85,\n'
            '      "affected_slides": ["..."],\n'
            '      "profile_coverage": "all profiles | weak + average | weak only",\n'
            '      "description": "<description>"\n'
            '    }}\n'
            '  ]\n'
            '}}'
        ),
    },
    "step5_recommend": {
        "system": (
            "You are the Recommendation Generation step of the Analytics & Adaptation pipeline.\n"
            "Your job: map ranked issues to concrete adaptation actions.\n\n"
            "Frozen Action Taxonomy (only use these 7 types):\n"
            "1. add_prerequisite_slide — add a prerequisite knowledge or intro slide\n"
            "2. add_example — add a worked example or concrete case\n"
            "3. rewrite_explanation — rewrite the explanation logic or terminology\n"
            "4. split_dense_slide — split an information-dense slide into two\n"
            "5. add_misconception_warning — add a misconception warning or boundary note\n"
            "6. mark_for_kb_review — escalate to Knowledge Bank for review\n"
            "7. regenerate_deck_section — trigger targeted regeneration of a section\n\n"
            "Rules:\n"
            "- Each recommendation targets ONE issue (but an issue may receive multiple actions).\n"
            "- Pick the MOST appropriate action_type based on the issue_type and context.\n"
            "- Write a clear rationale explaining why this action addresses the problem.\n"
            "- Assign priority: critical > high > medium > low, consistent with the issue severity.\n"
            "- Focus on top-ranked issues first; low-severity issues may get lighter treatment."
        ),
        "user": (
            "## Ranked Issues (sorted by severity)\n{ranked_issues_json}\n\n"
            "Generate adaptation recommendations for the top issues.\n\n"
            "Return JSON:\n"
            '{{\n'
            '  "recommendations": [\n'
            '    {{\n'
            '      "recommendation_id": "REC_001",\n'
            '      "target_issue_id": "ISS_001",\n'
            '      "action_type": "<one of the 7 frozen actions>",\n'
            '      "target_slides": ["slide_ref", ...],\n'
            '      "rationale": "<why this action helps>",\n'
            '      "priority": "critical|high|medium|low"\n'
            '    }}\n'
            '  ]\n'
            '}}'
        ),
    },
    "step6_proposal": {
        "system": (
            "You are the Proposal Candidate Generation step of the Analytics & Adaptation pipeline.\n"
            "Your job: package high-priority recommendations into formal proposal candidates for Governance Trace.\n\n"
            "Rules:\n"
            '- Only promote recommendations with priority "critical" or "high" to proposal candidates.\n'
            "- Each proposal candidate must include: target_deck_id, target_knowledge_ids, recommended_action, rationale, evidence_refs, suggested_priority.\n"
            "- The rationale should be self-contained — Governance Trace reviewers should understand the proposal without reading the full analytics chain.\n"
            "- Generate unique proposal_candidate_id (format: PC_001, PC_002, ...).\n"
            "- Also produce a cohort_insight summary object and a set of regenerate_hints for Content Generation.\n\n"
            "IMPORTANT BOUNDARY:\n"
            "- Analytics only GENERATES proposal candidates. It does NOT approve or reject them.\n"
            "- The proposal lifecycle (approved / rejected / frontier) belongs to Governance Trace."
        ),
        "user": (
            "## Recommendations\n{recommendations_json}\n\n"
            "## Ranked Issues\n{ranked_issues_json}\n\n"
            "## Deck Info\n"
            "- deck_id: {deck_id}\n"
            "- knowledge_ids: {knowledge_ids}\n"
            "- evidence_refs: {evidence_refs}\n\n"
            "Package the critical/high-priority recommendations into proposal candidates.\n"
            "Also produce a cohort_insight summary and regenerate_hints for Content Generation.\n\n"
            "Return JSON:\n"
            '{{\n'
            '  "cohort_insight": {{\n'
            '    "deck_id": "<deck_id>",\n'
            '    "weak_topic_rankings": [\n'
            '      {{"topic": "...", "severity": "...", "score": 0.0}}\n'
            '    ],\n'
            '    "confusion_clusters": [\n'
            '      {{"label": "...", "issue_count": 0, "summary": "..."}}\n'
            '    ],\n'
            '    "missing_prerequisites": ["..."],\n'
            '    "affected_slide_refs": ["..."]\n'
            '  }},\n'
            '  "proposal_candidates": [\n'
            '    {{\n'
            '      "proposal_candidate_id": "PC_001",\n'
            '      "target_deck_id": "<deck_id>",\n'
            '      "target_knowledge_ids": ["kb_xxx"],\n'
            '      "recommended_action": "<action_type>",\n'
            '      "rationale": "<self-contained explanation>",\n'
            '      "evidence_refs": ["run_xxx"],\n'
            '      "suggested_priority": "critical|high"\n'
            '    }}\n'
            '  ],\n'
            '  "regenerate_hints": [\n'
            '    {{\n'
            '      "target_slide": "slide_ref",\n'
            '      "action": "<action_type>",\n'
            '      "hint": "<what generation should do>"\n'
            '    }}\n'
            '  ]\n'
            '}}'
        ),
    },
}


# ╔══════════════════════════════════════════════════════════════╗
# ║  Part 3 — LLM Client (auto-detect provider)                 ║
# ╚══════════════════════════════════════════════════════════════╝

PROVIDER_CONFIG = {
    "DASHSCOPE_API_KEY": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "label": "阿里云百炼",
    },
    "OPENAI_API_KEY": {
        "base_url": None,
        "default_model": "gpt-4o-mini",
        "label": "OpenAI",
    },
    "GEMINI_API_KEY": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
        "label": "Google Gemini",
    },
}


def create_client():
    """Auto-detect available API key → return (client, default_model, provider_label)."""
    from openai import OpenAI

    for env_key, cfg in PROVIDER_CONFIG.items():
        api_key = os.environ.get(env_key)
        if api_key:
            kwargs = {"api_key": api_key}
            if cfg["base_url"]:
                kwargs["base_url"] = cfg["base_url"]
            return OpenAI(**kwargs), cfg["default_model"], cfg["label"]

    raise RuntimeError(
        "No API key found. Set one of:\n"
        + "\n".join(f"  export {k}='...'" for k in PROVIDER_CONFIG)
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║  Part 4 — LLM Pipeline (6-step agent reasoning)             ║
# ╚══════════════════════════════════════════════════════════════╝

class LLMPipeline:
    """6-step analytics pipeline driven by LLM + fixed prompts."""

    def __init__(self, model: str | None = None, verbose: bool = True):
        self.client, default_model, self.provider = create_client()
        self.model = model or default_model
        self.verbose = verbose
        self.trace: list[dict] = []

    def _call_llm(self, step_key: str, fmt_kwargs: dict, step_label: str) -> dict:
        prompts = PROMPTS[step_key]
        system = prompts["system"]
        user = prompts["user"].format(**fmt_kwargs)

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  Step: {step_label}")
            print(f"{'='*60}")

        t0 = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        elapsed = time.time() - t0
        result = json.loads(response.choices[0].message.content)

        usage = response.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0
        self.trace.append({
            "step": step_label, "model": self.model,
            "elapsed_sec": round(elapsed, 2),
            "tokens": {"prompt": pt, "completion": ct},
        })

        if self.verbose:
            print(f"  ✓ completed in {elapsed:.1f}s (prompt={pt}, completion={ct})")
        return result

    def run(
        self,
        signal: SignalSummary,
        deck: DeckMetadata,
        knowledge: list[KnowledgeEntry],
    ) -> dict:
        # Step 1 — Ingest Signal
        ingest = self._call_llm("step1_ingest", {
            "signal_json": signal.to_json(),
            "deck_json": json.dumps(asdict(deck), indent=2, ensure_ascii=False),
            "knowledge_json": json.dumps([asdict(k) for k in knowledge], indent=2, ensure_ascii=False),
        }, "1_ingest_signal")

        # Step 2 — Normalize Issues
        normalized = self._call_llm("step2_normalize", {
            "tagged_issues_json": json.dumps(ingest.get("tagged_issues", []), indent=2, ensure_ascii=False),
        }, "2_normalize_issues")

        # Step 3 — Cluster Issues
        clusters = self._call_llm("step3_cluster", {
            "normalized_issues_json": json.dumps(normalized.get("normalized_issues", []), indent=2, ensure_ascii=False),
        }, "3_cluster_issues")

        # Step 4 — Score Severity
        scored = self._call_llm("step4_score", {
            "normalized_issues_json": json.dumps(normalized.get("normalized_issues", []), indent=2, ensure_ascii=False),
            "clusters_json": json.dumps(clusters.get("issue_clusters", []), indent=2, ensure_ascii=False),
            "topic_scope": ", ".join(deck.topic_scope),
            "evidence_count": str(len(signal.evidence_refs)),
        }, "4_score_severity")

        # Step 5 — Generate Recommendations
        recommendations = self._call_llm("step5_recommend", {
            "ranked_issues_json": json.dumps(scored.get("ranked_issues", []), indent=2, ensure_ascii=False),
        }, "5_generate_recommendations")

        # Step 6 — Produce Proposal Candidates
        proposals = self._call_llm("step6_proposal", {
            "recommendations_json": json.dumps(recommendations.get("recommendations", []), indent=2, ensure_ascii=False),
            "ranked_issues_json": json.dumps(scored.get("ranked_issues", []), indent=2, ensure_ascii=False),
            "deck_id": deck.deck_id,
            "knowledge_ids": json.dumps(deck.source_knowledge_ids),
            "evidence_refs": json.dumps(signal.evidence_refs),
        }, "6_proposal_candidates")

        return {
            "step1_ingest": ingest,
            "step2_normalize": normalized,
            "step3_cluster": clusters,
            "step4_score": scored,
            "step5_recommend": recommendations,
            "step6_proposal": proposals,
            "trace": self.trace,
        }


# ╔══════════════════════════════════════════════════════════════╗
# ║  Part 5 — Rule-Based Fallback Engine (不需要 LLM)            ║
# ╚══════════════════════════════════════════════════════════════╝

class RuleBasedEngine:
    """Pure rule-based analytics — no LLM required, instant results.

    Useful as: offline fallback / baseline / quick demo / unit test fixture.
    """

    def run(self, signal: SignalSummary, deck: DeckMetadata) -> dict:
        issues = self._build_issues(signal, deck)
        recommendations = self._build_recommendations(signal, issues)
        proposals = self._build_proposals(signal, recommendations)
        return {
            "deck_id": signal.tested_deck_id,
            "issues": [asdict(i) for i in issues],
            "recommendations": [asdict(r) for r in recommendations],
            "proposal_candidates": [asdict(p) for p in proposals],
        }

    # ── internal ──

    def _build_issues(self, signal: SignalSummary, deck: DeckMetadata) -> list:
        issues = []

        for topic in signal.weak_topics:
            score = 60
            if self._has_related(topic, signal.repeated_confusion_points):
                score += 10
            if self._has_related(topic, signal.misconception_clusters):
                score += 10
            if signal.missing_prerequisite_patterns:
                score += 5
            issues.append(self._issue(
                "weak_topic", topic, score, deck.slide_refs, signal.evidence_refs,
                f"Topic '{topic}' appears in weak_topics and is repeatedly problematic.",
            ))

        for text in signal.repeated_confusion_points:
            issues.append(self._issue(
                "confusion", self._guess_topic(text, signal.weak_topics),
                75, deck.slide_refs, signal.evidence_refs,
                f"Students repeatedly confused about: {text}",
            ))

        for text in signal.misconception_clusters:
            issues.append(self._issue(
                "misconception", self._guess_topic(text, signal.weak_topics),
                80, deck.slide_refs, signal.evidence_refs,
                f"Recurring misconception: {text}",
            ))

        for text in signal.missing_prerequisite_patterns:
            issues.append(self._issue(
                "missing_prerequisite", self._guess_topic(text, signal.weak_topics),
                88, deck.slide_refs, signal.evidence_refs,
                f"Missing prerequisite knowledge: {text}",
            ))

        return sorted(issues, key=lambda x: x.score, reverse=True)

    def _build_recommendations(self, signal, issues):
        recs = []
        for iss in issues:
            action = self._map_action(iss)
            score = min(100, iss.score + ACTION_PRIORITY.get(action, 50) // 10)
            recs.append(_Rec(
                recommendation_id=_uid("rec"), action=action,
                priority=self._priority(score), score=score,
                target_deck_id=signal.tested_deck_id,
                target_slide_refs=iss.affected_slide_refs,
                target_knowledge_ids=signal.recommended_revision_targets[:3],
                rationale=iss.rationale, evidence_refs=iss.evidence_refs,
                source_issue_ids=[iss.issue_id],
            ))
        if len(issues) >= 4:
            recs.append(_Rec(
                recommendation_id=_uid("rec"), action="regenerate_deck_section",
                priority="medium", score=68, target_deck_id=signal.tested_deck_id,
                target_slide_refs=signal.recommended_revision_targets[:3],
                target_knowledge_ids=[], rationale="Multiple issue types across same section.",
                evidence_refs=signal.evidence_refs,
                source_issue_ids=[i.issue_id for i in issues[:3]],
            ))
        best: dict[str, _Rec] = {}
        for r in recs:
            if r.action not in best or r.score > best[r.action].score:
                best[r.action] = r
        return sorted(best.values(), key=lambda x: x.score, reverse=True)

    def _build_proposals(self, signal, recs):
        return [
            _Proposal(
                proposal_candidate_id=_uid("pc"), target_deck_id=signal.tested_deck_id,
                target_knowledge_ids=r.target_knowledge_ids,
                recommended_action=r.action, rationale=r.rationale,
                evidence_refs=r.evidence_refs, suggested_priority=r.priority,
                based_on_issue_ids=r.source_issue_ids,
            )
            for r in recs if r.priority in ("high", "critical")
        ]

    def _map_action(self, iss) -> str:
        candidates = ISSUE_TO_ACTIONS.get(iss.issue_type, [])
        return candidates[0] if candidates else "mark_for_kb_review"

    def _issue(self, itype, topic, score, slides, evidence, rationale):
        return _Issue(
            issue_id=_uid("issue"), issue_type=itype, topic=topic,
            severity=self._severity(score), score=score,
            affected_slide_refs=slides, rationale=rationale,
            evidence_refs=evidence,
        )

    @staticmethod
    def _severity(score: int) -> str:
        if score >= 85: return "critical"
        if score >= 75: return "high"
        if score >= 65: return "medium"
        return "low"

    @staticmethod
    def _priority(score: int) -> str:
        if score >= 85: return "high"
        if score >= 70: return "medium"
        return "low"

    @staticmethod
    def _guess_topic(text: str, topics: list[str]) -> str:
        t = text.lower()
        for topic in topics:
            if topic.lower() in t:
                return topic
        return topics[0] if topics else "unknown"

    @staticmethod
    def _has_related(topic: str, items: list[str]) -> bool:
        t = topic.lower()
        return any(t in item.lower() for item in items)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class _Issue:
    issue_id: str
    issue_type: str
    topic: str
    severity: str
    score: int
    affected_slide_refs: list[str]
    rationale: str
    evidence_refs: list[str]

@dataclass
class _Rec:
    recommendation_id: str
    action: str
    priority: str
    score: int
    target_deck_id: str
    target_slide_refs: list[str]
    target_knowledge_ids: list[str]
    rationale: str
    evidence_refs: list[str]
    source_issue_ids: list[str]

@dataclass
class _Proposal:
    proposal_candidate_id: str
    target_deck_id: str
    target_knowledge_ids: list[str]
    recommended_action: str
    rationale: str
    evidence_refs: list[str]
    suggested_priority: str
    based_on_issue_ids: list[str]
