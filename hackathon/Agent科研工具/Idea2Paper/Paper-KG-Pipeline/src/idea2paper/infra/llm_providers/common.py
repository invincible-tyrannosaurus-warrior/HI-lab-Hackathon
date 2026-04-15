import json
from typing import Any, Dict, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SENSITIVE_KEYS = {
    "authorization",
    "x-api-key",
    "x-goog-api-key",
    "api-key",
    "apikey",
    "api_key",
    "token",
    "secret",
}


def build_session_with_retries() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def join_url(base: str, path: str) -> str:
    if not base:
        return path
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def extract_json_safely(resp: requests.Response) -> Tuple[Dict[str, Any], str]:
    try:
        return resp.json(), ""
    except Exception:
        return {}, resp.text if resp is not None else ""


def _to_dict(value) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        return json.loads(text)
    return {}


def parse_extra(value) -> Tuple[Dict[str, Any], str]:
    try:
        return _to_dict(value), ""
    except Exception as e:
        return {}, f"invalid extra config: {e}"


def merge_dict(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    if not extra:
        return dict(base)
    out = dict(base)
    out.update(extra)
    return out


def redact_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    redacted = {}
    for k, v in mapping.items():
        key_lower = str(k).lower()
        if key_lower in SENSITIVE_KEYS or "token" in key_lower or "key" in key_lower or "secret" in key_lower:
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted
