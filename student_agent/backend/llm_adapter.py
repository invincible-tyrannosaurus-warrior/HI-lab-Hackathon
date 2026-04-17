from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional


class LLMClient(ABC):
    @abstractmethod
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        temperature: float = 0.2,
        provider_order: Optional[list[str]] = None,
        allow_fallbacks: bool = True,
    ) -> dict:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        temperature: float = 0.2,
        provider_order: Optional[list[str]] = None,
        allow_fallbacks: bool = True,
    ) -> dict:
        raise NotImplementedError("Mock client is not used directly. Use mock_student_response instead.")


class OpenRouterLLMClient(LLMClient):
    def __init__(self, model: str = "qwen/qwen-2.5-7b-instruct", api_key: Optional[str] = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.http_referer = os.getenv("OPENROUTER_HTTP_REFERER")
        self.app_title = os.getenv("OPENROUTER_APP_TITLE", "Student Agent Testing MVP")

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        temperature: float = 0.2,
        provider_order: Optional[list[str]] = None,
        allow_fallbacks: bool = True,
    ) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        extra_headers = {}
        if self.http_referer:
            extra_headers["HTTP-Referer"] = self.http_referer
        if self.app_title:
            extra_headers["X-Title"] = self.app_title

        extra_body = {
            "provider": {
                "allow_fallbacks": allow_fallbacks,
                "require_parameters": True,
            }
        }
        if provider_order:
            extra_body["provider"]["order"] = provider_order
            extra_body["provider"]["only"] = provider_order

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "strict": True,
                        "schema": response_schema,
                    }
                },
                extra_headers=extra_headers or None,
                extra_body=extra_body,
            )
            content = self._extract_content(response)
            return json.loads(content)
        except Exception as first_error:
            fallback_messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        user_prompt
                        + "\n\nReturn a single valid JSON object only. Do not wrap it in markdown fences."
                    ),
                },
            ]
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=fallback_messages,
                    extra_headers=extra_headers or None,
                    extra_body=extra_body,
                )
                content = self._extract_content(response)
                return json.loads(self._strip_code_fences(content))
            except Exception as fallback_error:
                raise RuntimeError(
                    f"OpenRouter structured request failed: {first_error}; fallback JSON mode failed: {fallback_error}"
                ) from fallback_error

    @staticmethod
    def _extract_content(response) -> str:
        content = None
        if getattr(response, "choices", None):
            message = response.choices[0].message
            content = getattr(message, "content", None)
        if not content:
            raise RuntimeError("Model returned no message content.")
        return content

    @staticmethod
    def _strip_code_fences(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return stripped
