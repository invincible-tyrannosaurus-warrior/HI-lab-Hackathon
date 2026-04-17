from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from backend.config import (
    get_embedding_api_key,
    get_embedding_backend,
    get_embedding_base_url,
    get_embedding_batch_size,
    get_embedding_model,
    get_embedding_provider_only,
)


class EmbeddingClient(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class MockEmbeddingClient:
    """Deterministic test-only embedder that avoids external API calls."""

    dimension = 64

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        payload = (text or "").encode("utf-8", errors="replace")
        for index in range(self.dimension):
            digest = hashlib.sha256(payload + index.to_bytes(2, "big")).digest()
            values[index] = int.from_bytes(digest[:4], "big") / 2**32
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class OpenRouterEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        batch_size: int,
        provider_only: list[str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.batch_size = batch_size
        self.provider_only = provider_only or None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        results: list[list[float]] = []
        with httpx.Client(timeout=60.0) as client:
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                payload = {
                    "model": self.model,
                    "input": batch,
                    "encoding_format": "float",
                }
                if self.provider_only:
                    payload["provider"] = {
                        "only": self.provider_only,
                        "allow_fallbacks": True,
                        "data_collection": "deny",
                    }
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                payload = response.json()
                ordered = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
                results.extend(item["embedding"] for item in ordered)
        return results


_embedding_client: EmbeddingClient | None = None
_embedding_signature: tuple[str, str | None, str, str] | None = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client, _embedding_signature

    backend = get_embedding_backend()
    signature = (
        backend,
        get_embedding_api_key(),
        get_embedding_base_url(),
        get_embedding_model(),
        ",".join(get_embedding_provider_only() or []),
    )
    if _embedding_client is not None and _embedding_signature == signature:
        return _embedding_client

    if backend == "mock":
        _embedding_client = MockEmbeddingClient()
    elif backend == "openrouter":
        api_key = get_embedding_api_key()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required when KB_EMBEDDING_BACKEND=openrouter")
        _embedding_client = OpenRouterEmbeddingClient(
            api_key=api_key,
            base_url=get_embedding_base_url(),
            model=get_embedding_model(),
            batch_size=get_embedding_batch_size(),
            provider_only=get_embedding_provider_only(),
        )
    else:
        raise RuntimeError(f"Unsupported embedding backend: {backend}")

    _embedding_signature = signature
    return _embedding_client


def reset_embedding_client() -> None:
    global _embedding_client, _embedding_signature
    _embedding_client = None
    _embedding_signature = None
