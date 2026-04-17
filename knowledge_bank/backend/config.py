from __future__ import annotations

import os
from pathlib import Path

DEFAULT_VECTOR_ROOT = Path(__file__).resolve().parent / "storage" / "vector" / "chroma"
DEFAULT_PROCESSED_ROOT = Path(__file__).resolve().parent / "storage" / "processed"
DEFAULT_EMBEDDING_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-large"


def get_vector_store_root() -> Path:
    root = Path(os.getenv("KB_VECTOR_STORE_ROOT", DEFAULT_VECTOR_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_processed_storage_root() -> Path:
    root = Path(os.getenv("KB_PROCESSED_ROOT", DEFAULT_PROCESSED_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_vector_backend() -> str:
    return os.getenv("KB_VECTOR_BACKEND", "chroma").strip().lower()


def get_embedding_backend() -> str:
    return os.getenv("KB_EMBEDDING_BACKEND", "openrouter").strip().lower()


def get_embedding_base_url() -> str:
    return os.getenv("OPENROUTER_BASE_URL", DEFAULT_EMBEDDING_BASE_URL).rstrip("/")


def get_embedding_model() -> str:
    return os.getenv("OPENROUTER_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def get_embedding_api_key() -> str | None:
    return os.getenv("OPENROUTER_API_KEY")


def get_embedding_provider_only() -> list[str] | None:
    configured = os.getenv("OPENROUTER_PROVIDER_ONLY", "").strip()
    if configured:
        providers = [item.strip() for item in configured.split(",") if item.strip()]
        return providers or None

    model = get_embedding_model()
    if model.startswith("openai/"):
        return ["openai"]
    return None


def get_chunk_size() -> int:
    return int(os.getenv("KB_CHUNK_SIZE", "1000"))


def get_chunk_overlap() -> int:
    return int(os.getenv("KB_CHUNK_OVERLAP", "100"))


def get_embedding_batch_size() -> int:
    return int(os.getenv("KB_EMBEDDING_BATCH_SIZE", "16"))


def get_source_chunk_index_batch_size() -> int:
    return int(os.getenv("KB_SOURCE_CHUNK_INDEX_BATCH_SIZE", "16"))


def get_context_bundle_top_k() -> int:
    return int(os.getenv("KB_CONTEXT_BUNDLE_TOP_K", "8"))
