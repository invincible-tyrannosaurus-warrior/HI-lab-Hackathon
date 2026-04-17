from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from backend.config import get_vector_backend, get_vector_store_root


@dataclass(frozen=True)
class VectorSearchHit:
    id: str
    document: str
    metadata: dict[str, Any]
    score: float


class VectorStore(Protocol):
    backend_name: str

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        ...

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        ...

    def reset(self) -> None:
        ...


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)


def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if expected is None:
            continue
        if metadata.get(key) != expected:
            return False
    return True


class InMemoryVectorStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        collection = self._collections.setdefault(collection_name, {})
        for record_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            collection[record_id] = {
                "id": record_id,
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        collection = self._collections.get(collection_name, {})
        hits = []
        for item in collection.values():
            if not _matches_filters(item["metadata"], filters):
                continue
            score = _cosine_similarity(query_embedding, item["embedding"])
            hits.append(
                VectorSearchHit(
                    id=item["id"],
                    document=item["document"],
                    metadata=item["metadata"],
                    score=score,
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.id))
        return hits[:top_k]

    def reset(self) -> None:
        self._collections = {}


class ChromaVectorStore:
    backend_name = "chroma"

    def __init__(self, persist_path: str) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("chromadb is required when KB_VECTOR_BACKEND=chroma") from exc

        self._chromadb = chromadb
        self._client = chromadb.PersistentClient(path=persist_path)

    def _collection(self, name: str):
        return self._client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def _build_where(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        items = [{key: value} for key, value in filters.items() if value is not None]
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        return {"$and": items}

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._collection(collection_name).upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        response = self._collection(collection_name).query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=self._build_where(filters),
        )
        ids = response.get("ids", [[]])[0]
        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]
        hits: list[VectorSearchHit] = []
        for record_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            score = 1.0 - float(distance)
            hits.append(
                VectorSearchHit(
                    id=record_id,
                    document=document,
                    metadata=metadata or {},
                    score=score,
                )
            )
        return hits

    def reset(self) -> None:
        self._client.reset()


_vector_store: VectorStore | None = None
_vector_signature: tuple[str, str] | None = None


def get_vector_store() -> VectorStore:
    global _vector_store, _vector_signature

    backend = get_vector_backend()
    persist_path = str(get_vector_store_root())
    signature = (backend, persist_path)
    if _vector_store is not None and _vector_signature == signature:
        return _vector_store

    if backend == "memory":
        _vector_store = InMemoryVectorStore()
    elif backend == "chroma":
        _vector_store = ChromaVectorStore(persist_path)
    else:
        raise RuntimeError(f"Unsupported vector backend: {backend}")

    _vector_signature = signature
    return _vector_store


def reset_vector_store() -> None:
    global _vector_store, _vector_signature
    if _vector_store is not None:
        _vector_store.reset()
    _vector_store = None
    _vector_signature = None
