"""
Lightweight LLM helpers used by KG build scripts.
Falls back to a local implementation when idea2paper is not installed.
"""

import json
import os
import re

try:
    from idea2paper.infra.llm import *  # noqa: F401,F403
except ImportError:
    from openai import OpenAI

    def call_llm(
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("SILICONFLOW_API_KEY")
            or ""
        )
        base_url = os.getenv("OPENAI_BASE_URL") or None
        model = os.getenv("OPENAI_MODEL", "gpt-4o")

        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()

    def parse_json_from_llm(text: str) -> dict | None:
        """Extract the first JSON object from LLM output."""
        if not text:
            return None
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting from markdown code block
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Try finding first { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return None
