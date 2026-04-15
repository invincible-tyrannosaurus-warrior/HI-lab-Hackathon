from typing import Any, Dict

from .common import build_session_with_retries, extract_json_safely, join_url, merge_dict


def call_openai_responses(
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
    endpoint = api_url or join_url(base_url or "https://api.openai.com/v1", "/responses")
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
            "input": prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
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

        if "output_text" in data and isinstance(data.get("output_text"), str):
            return {"ok": True, "text": data.get("output_text", ""), "error": "", "url": endpoint}

        output = data.get("output", [])
        texts = []
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "output_text":
                        text = block.get("text")
                        if isinstance(text, str):
                            texts.append(text)
        if texts:
            return {"ok": True, "text": "\n".join(texts), "error": "", "url": endpoint}

        return {"ok": False, "text": "", "error": "missing output_text in response", "url": endpoint}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e), "url": endpoint}
    finally:
        session.close()
