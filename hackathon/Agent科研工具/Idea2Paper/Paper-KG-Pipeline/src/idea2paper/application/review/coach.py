from __future__ import annotations

from typing import Dict, Optional

from idea2paper.config import PipelineConfig
from idea2paper.infra.llm import call_llm, parse_json_from_llm
from idea2paper.infra.run_context import get_logger


class CoachReviewer:
    def __init__(self):
        self.logger = get_logger()

    def _log_event(self, event_type: str, payload: Dict):
        if self.logger:
            self.logger.log_event(event_type, payload)

    def _build_prompt(self, story: Dict, role_scores: Dict[str, float], main_issue: str) -> str:
        return f"""
You are a strict research writing coach. Provide field-level, actionable edits.
Do NOT output any numeric overall scores. Focus on concrete fixes.

Role scores (for context only): {role_scores}
Main issue: {main_issue}

Story:
Title: {story.get('title', '')}
Abstract: {story.get('abstract', '')}
Problem: {story.get('problem_framing') or story.get('problem_definition','')}
Method: {story.get('method_skeleton', '')}
Innovation Claims: {story.get('innovation_claims', '')}
Experiments Plan: {story.get('experiments_plan', '')}

Return JSON ONLY with this schema:
{{
  "field_feedback": {{
    "title": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "abstract": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "problem_framing": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "method_skeleton": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "innovation_claims": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "experiments_plan": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}}
  }},
  "suggested_edits": [
    {{"field":"innovation_claims","action":"rewrite|add|delete|expand","content":"..."}}
  ],
  "priority": ["innovation_claims","method_skeleton","abstract"]
}}
"""

    def _validate(self, result: Dict) -> Optional[Dict]:
        if not isinstance(result, dict):
            return None
        field_feedback = result.get("field_feedback")
        if not isinstance(field_feedback, dict):
            return None
        suggested_edits = result.get("suggested_edits") or []
        priority = result.get("priority") or []
        return {
            "field_feedback": field_feedback,
            "suggested_edits": suggested_edits if isinstance(suggested_edits, list) else [],
            "priority": priority if isinstance(priority, list) else [],
        }

    def review(self, story: Dict, role_scores: Dict[str, float], main_issue: str) -> Dict:
        if not getattr(PipelineConfig, "CRITIC_COACH_ENABLE", True):
            return {"field_feedback": {}, "suggested_edits": [], "priority": []}

        prompt = self._build_prompt(story, role_scores, main_issue)
        response = call_llm(
            prompt,
            temperature=getattr(PipelineConfig, "CRITIC_COACH_TEMPERATURE", 0.3),
            max_tokens=getattr(PipelineConfig, "CRITIC_COACH_MAX_TOKENS", 4096),
            timeout=180,
        )
        result = parse_json_from_llm(response)
        normalized = self._validate(result) if result else None
        if normalized:
            return normalized

        print("    ⚠️  Coach 输出不合规：开始修复重试…")
        retries = getattr(PipelineConfig, "CRITIC_JSON_RETRIES", 2)
        last_response = response
        for attempt in range(1, retries + 1):
            print(f"    🔧 Coach 修复重试：attempt={attempt}/{retries}")
            repair_prompt = f"""
Fix the previous output into STRICT valid JSON only.
Return JSON ONLY with schema:
{{
  "field_feedback": {{
    "title": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "abstract": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "problem_framing": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "method_skeleton": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "innovation_claims": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}},
    "experiments_plan": {{"issue":"...", "edit_instruction":"...", "expected_effect":"..."}}
  }},
  "suggested_edits": [
    {{"field":"innovation_claims","action":"rewrite|add|delete|expand","content":"..."}}
  ],
  "priority": ["innovation_claims","method_skeleton","abstract"]
}}

Previous output:
{last_response[:6000]}
"""
            response = call_llm(
                repair_prompt,
                temperature=PipelineConfig.LLM_TEMPERATURE_CRITIC_REPAIR,
                max_tokens=getattr(PipelineConfig, "CRITIC_COACH_MAX_TOKENS", 4096),
                timeout=180,
            )
            result = parse_json_from_llm(response)
            normalized = self._validate(result) if result else None
            if normalized:
                return normalized
            last_response = response
            self._log_event("coach_invalid_output", {"attempt": attempt})

        if getattr(PipelineConfig, "CRITIC_STRICT_JSON", True):
            raise RuntimeError("Coach JSON invalid after retries.")
        return {"field_feedback": {}, "suggested_edits": [], "priority": []}
