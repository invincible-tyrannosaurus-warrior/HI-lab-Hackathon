from typing import Any, Dict

from .common import build_session_with_retries, extract_json_safely, join_url, merge_dict


def call_gemini(
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
    if api_url:
        endpoint = api_url
    else:
        base = base_url or "https://generativelanguage.googleapis.com/v1beta"
        endpoint = join_url(base, f"/models/{model}:generateContent")

    headers = merge_dict(
        {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        extra_headers or {},
    )
    payload = merge_dict(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        },
        extra_body or {},
    )

    session = build_session_with_retries()
    try:
        resp = session.post(endpoint, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data, raw_text = extract_json_safely(resp)
        if not isinstance(data, dict):
            return {"ok": False, "text": "", "error": f"invalid response: {raw_text[:200]}", "url": endpoint}
        candidates = data.get("candidates", [])
        if not candidates:
            return {"ok": False, "text": "", "error": "no candidates in response", "url": endpoint}
        content = candidates[0].get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        texts = []
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part.get("text"))
        if texts:
            return {"ok": True, "text": "\n".join(texts), "error": "", "url": endpoint}
        return {"ok": False, "text": "", "error": "missing text parts in response", "url": endpoint}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "url": endpoint}
    finally:
        session.close()
