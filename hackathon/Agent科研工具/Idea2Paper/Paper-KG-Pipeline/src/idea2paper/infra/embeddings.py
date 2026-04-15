import time
from typing import Optional, List

import requests

from idea2paper.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_API_URL,
    EMBEDDING_MODEL,
)
from idea2paper.infra.run_context import get_logger


EMBEDDING_PROVIDER_FOR_LOG = "openai_compatible"


def get_embedding(text: str, logger=None, timeout: int = 120) -> Optional[List[float]]:
    """Get embedding for text using OpenAI-compatible embeddings API.

    Returns None on failure (no exception thrown).
    """
    if logger is None:
        logger = get_logger()
    start_ts = time.time()

    if not EMBEDDING_API_KEY:
        if logger:
            logger.log_embedding_call(
                request={
                    "provider": EMBEDDING_PROVIDER_FOR_LOG,
                    "url": EMBEDDING_API_URL,
                    "model": EMBEDDING_MODEL,
                    "input_preview": text,
                    "timeout": timeout,
                    "simulated": True
                },
                response={
                    "ok": False,
                    "latency_ms": int((time.time() - start_ts) * 1000),
                    "error": "EMBEDDING_API_KEY not configured"
                }
            )
        return None

    headers = {
        "Authorization": f"Bearer {EMBEDDING_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text
    }

    try:
        resp = requests.post(EMBEDDING_API_URL, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        emb = data["data"][0]["embedding"]
        if logger:
            logger.log_embedding_call(
                request={
                    "provider": EMBEDDING_PROVIDER_FOR_LOG,
                    "url": EMBEDDING_API_URL,
                    "model": EMBEDDING_MODEL,
                    "input_preview": text,
                    "timeout": timeout,
                    "simulated": False
                },
                response={
                    "ok": True,
                    "latency_ms": int((time.time() - start_ts) * 1000)
                }
            )
        return emb
    except Exception as e:
        if logger:
            logger.log_embedding_call(
                request={
                    "provider": EMBEDDING_PROVIDER_FOR_LOG,
                    "url": EMBEDDING_API_URL,
                    "model": EMBEDDING_MODEL,
                    "input_preview": text,
                    "timeout": timeout,
                    "simulated": False
                },
                response={
                    "ok": False,
                    "latency_ms": int((time.time() - start_ts) * 1000),
                    "error": str(e)
                }
            )
        return None


def _preview_texts(texts: List[str], max_chars: int = 200) -> List[str]:
    previews = []
    for t in texts:
        if t is None:
            previews.append("")
            continue
        s = str(t)
        if len(s) > max_chars:
            previews.append(s[:max_chars] + "...(truncated)")
        else:
            previews.append(s)
    return previews


def get_embeddings_batch(texts: List[str], logger=None, timeout: int = 120) -> Optional[List[List[float]]]:
    """Get embeddings for a batch of texts. Returns None on failure."""
    if logger is None:
        logger = get_logger()
    start_ts = time.time()

    if not EMBEDDING_API_KEY:
        if logger:
            logger.log_embedding_call(
                request={
                    "provider": EMBEDDING_PROVIDER_FOR_LOG,
                    "url": EMBEDDING_API_URL,
                    "model": EMBEDDING_MODEL,
                    "input_preview": _preview_texts(texts),
                    "timeout": timeout,
                    "simulated": True,
                    "batch_size": len(texts),
                },
                response={
                    "ok": False,
                    "latency_ms": int((time.time() - start_ts) * 1000),
                    "error": "EMBEDDING_API_KEY not configured"
                }
            )
        return None

    headers = {
        "Authorization": f"Bearer {EMBEDDING_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts
    }

    try:
        resp = requests.post(EMBEDDING_API_URL, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        embs = [item["embedding"] for item in data.get("data", [])]
        if len(embs) != len(texts):
            raise ValueError(f"embedding batch size mismatch: got {len(embs)} expected {len(texts)}")
        if logger:
            logger.log_embedding_call(
                request={
                    "provider": EMBEDDING_PROVIDER_FOR_LOG,
                    "url": EMBEDDING_API_URL,
                    "model": EMBEDDING_MODEL,
                    "input_preview": _preview_texts(texts),
                    "timeout": timeout,
                    "simulated": False,
                    "batch_size": len(texts),
                },
                response={
                    "ok": True,
                    "latency_ms": int((time.time() - start_ts) * 1000)
                }
            )
        return embs
    except Exception as e:
        if logger:
            logger.log_embedding_call(
                request={
                    "provider": EMBEDDING_PROVIDER_FOR_LOG,
                    "url": EMBEDDING_API_URL,
                    "model": EMBEDDING_MODEL,
                    "input_preview": _preview_texts(texts),
                    "timeout": timeout,
                    "simulated": False,
                    "batch_size": len(texts),
                },
                response={
                    "ok": False,
                    "latency_ms": int((time.time() - start_ts) * 1000),
                    "error": str(e)
                }
            )
        return None
