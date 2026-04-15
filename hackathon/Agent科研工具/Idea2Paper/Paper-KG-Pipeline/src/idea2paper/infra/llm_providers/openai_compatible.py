from typing import Any, Dict

from .common import build_session_with_retries, extract_json_safely, join_url, merge_dict


def call_openai_compatible_chat(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    api_url: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    extra_headers: Dict[str, Any] | None = None,
    extra_body: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    endpoint = api_url or join_url(base_url or "https://api.openai.com/v1", "/chat/completions")
    headers = merge_dict(
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        extra_headers or {},
    )
    payload = merge_dict(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        extra_body or {},
    )

    session = build_session_with_retries()
    try:
        resp = session.post(endpoint, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data, raw_text = extract_json_safely(resp)
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            return {"ok": False, "text": "", "error": f"invalid response: {raw_text[:200]}", "url": endpoint}
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if message and isinstance(message, dict) and "content" in message:
            return {"ok": True, "text": message.get("content", ""), "error": "", "url": endpoint}
        if isinstance(choices[0], dict) and "text" in choices[0]:
            return {"ok": True, "text": choices[0].get("text", ""), "error": "", "url": endpoint}
        return {"ok": False, "text": "", "error": "missing content in choices", "url": endpoint}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "url": endpoint}
    finally:
        session.close()
