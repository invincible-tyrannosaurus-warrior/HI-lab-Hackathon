from __future__ import annotations

from typing import Dict, List, Tuple

from idea2paper.config import PipelineConfig
from idea2paper.infra.llm import call_llm, parse_json_from_llm
from idea2paper.infra.run_context import get_logger

from .rubric import get_rubric, RUBRIC_VERSION


FORBIDDEN_TERMS = ("score", "score10", "paper_id", "title", "author", "link", "doi", "arxiv", "pattern_id")


def _format_card(card: Dict) -> str:
    lines = []
    for key in ["problem", "method", "contrib"]:
        value = card.get(key, "")
        if value:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) if lines else "- (empty)"


def _contains_forbidden(text: str) -> bool:
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in FORBIDDEN_TERMS)


class BlindJudge:
    def __init__(self):
        self.logger = get_logger()

    def _log_event(self, event_type: str, payload: Dict):
        if self.logger:
            self.logger.log_event(event_type, payload)

    def _build_prompt(self, role: str, story_card: Dict, anchor_cards: List[Dict], anchor_ids: List[str]) -> str:
        rubric = get_rubric(role)
        anchor_blocks = []
        for anchor_id, card in zip(anchor_ids, anchor_cards):
            anchor_blocks.append(f"{anchor_id}:\n{_format_card(card)}")
        anchors_text = "\n\n".join(anchor_blocks)

        return f"""
You are a strict reviewer focused on **{role}**.
You MUST NOT output any numeric score, paper title, author, link, paper_id, or any real-world identifiers.
You are given a Story card and multiple anonymous Anchor cards. Compare the Story against each Anchor on the rubric.
Do NOT treat missing/shorter text as evidence of lower quality. If evidence is insufficient, prefer tie (weak).
Do NOT award "better" solely because one card is more detailed/longer; cite substantive quality differences.

Rubric ({role}):
{rubric}

Story Card:
{_format_card(story_card)}

Anchor Cards:
{anchors_text}

Task:
For EACH anchor, output a judgement of the Story vs that Anchor on {role}:
- judgement: better | tie | worse
- strength: weak | medium | strong
- rationale: <= 25 words, refer ONLY to card content. Do NOT mention scores or identifiers.

Return JSON ONLY:
{{
  "rubric_version": "{RUBRIC_VERSION}",
  "comparisons": [
    {{"anchor_id": "A1", "judgement": "better|tie|worse", "strength": "weak|medium|strong", "rationale": "..."}}
  ]
}}
"""

    def _build_repair_prompt(self, previous_text: str, anchor_ids: List[str]) -> str:
        return f"""
Fix the previous output into STRICT valid JSON only.
Rules:
1) Output JSON ONLY (no markdown, no explanation).
2) "comparisons" length MUST equal number of anchors.
3) anchor_id MUST be one of: {", ".join(anchor_ids)}.
4) judgement must be one of: better|tie|worse.
5) strength must be one of: weak|medium|strong.
6) rationale must be <= 25 words and MUST NOT mention scores or identifiers.
7) Do NOT use missing/shorter text as the sole reason for better; if evidence is insufficient, prefer tie.

Previous output:
{previous_text[:6000]}

Return ONLY the corrected JSON:
{{
  "rubric_version": "{RUBRIC_VERSION}",
  "comparisons": [
    {{"anchor_id": "A1", "judgement": "better|tie|worse", "strength": "weak|medium|strong", "rationale": "..."}}
  ]
}}
"""

    def _validate(self, result: Dict, anchor_ids: List[str]) -> Tuple[bool, str, Dict]:
        if not isinstance(result, dict):
            return False, "schema_invalid", {}
        comparisons = result.get("comparisons")
        if not isinstance(comparisons, list):
            return False, "schema_invalid", {}

        valid_ids = set(anchor_ids)
        seen = set()
        normalized = []
        for comp in comparisons:
            if not isinstance(comp, dict):
                continue
            anchor_id = comp.get("anchor_id")
            if anchor_id not in valid_ids or anchor_id in seen:
                continue
            judgement = comp.get("judgement")
            strength = comp.get("strength")
            rationale = comp.get("rationale")
            if judgement not in ("better", "tie", "worse"):
                return False, "schema_invalid", {}
            if strength not in ("weak", "medium", "strong"):
                return False, "schema_invalid", {}
            if not isinstance(rationale, str) or not rationale.strip():
                return False, "schema_invalid", {}
            if len(rationale.split()) > 25:
                return False, "rationale_too_long", {}
            if _contains_forbidden(rationale):
                return False, "rationale_contains_forbidden", {}
            normalized.append({
                "anchor_id": anchor_id,
                "judgement": judgement,
                "strength": strength,
                "rationale": rationale.strip(),
            })
            seen.add(anchor_id)

        if len(seen) != len(valid_ids):
            return False, "missing_anchors", {}

        ordered = []
        for aid in anchor_ids:
            for comp in normalized:
                if comp["anchor_id"] == aid:
                    ordered.append(comp)
                    break

        return True, "", {"comparisons": ordered}

    def judge(self, role: str, story_card: Dict, anchor_cards: List[Dict]) -> Dict:
        anchor_ids = [f"A{i+1}" for i in range(len(anchor_cards))]
        prompt = self._build_prompt(role, story_card, anchor_cards, anchor_ids)
        response = call_llm(
            prompt,
            temperature=PipelineConfig.LLM_TEMPERATURE_CRITIC_MAIN,
            max_tokens=4096,
            timeout=180,
        )
        result = parse_json_from_llm(response)
        ok, reason, normalized = (False, "parse_failed", {})
        if result:
            ok, reason, normalized = self._validate(result, anchor_ids)

        if ok:
            return normalized

        print(f"    ⚠️  BlindJudge 输出不合规：role={role} | reason={reason} | 开始修复重试…")
        self._log_event("blind_judge_invalid", {
            "role": role,
            "reason": reason,
            "response_len": len(response),
        })

        retries = getattr(PipelineConfig, "CRITIC_JSON_RETRIES", 2)
        last_reason = reason
        last_response = response
        for attempt in range(1, retries + 1):
            print(f"    🔧 BlindJudge 修复重试：role={role} | attempt={attempt}/{retries}")
            prompt = self._build_repair_prompt(last_response, anchor_ids)
            response = call_llm(
                prompt,
                temperature=PipelineConfig.LLM_TEMPERATURE_CRITIC_REPAIR,
                max_tokens=4096,
                timeout=180,
            )
            result = parse_json_from_llm(response)
            ok, reason, normalized = (False, "parse_failed", {})
            if result:
                ok, reason, normalized = self._validate(result, anchor_ids)
            if ok:
                self._log_event("blind_judge_recovered", {"role": role, "attempt": attempt})
                return normalized
            last_reason = reason
            last_response = response
            self._log_event("blind_judge_invalid", {
                "role": role,
                "attempt": attempt,
                "reason": reason,
            })

        if getattr(PipelineConfig, "CRITIC_STRICT_JSON", True):
            raise RuntimeError(f"Blind judge JSON invalid after retries: role={role}, reason={last_reason}")

        neutral = [{
            "anchor_id": aid,
            "judgement": "tie",
            "strength": "weak",
            "rationale": "Unable to parse; neutral comparison.",
        } for aid in anchor_ids]
        return {"comparisons": neutral}
