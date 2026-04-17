from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from backend.config import (
    get_chunk_overlap,
    get_chunk_size,
    get_embedding_batch_size,
    get_processed_storage_root,
    get_source_chunk_index_batch_size,
)
from backend.models.knowledge_unit import KnowledgeUnit
from backend.models.source import Source
from backend.schemas.common import loads_json_list
from backend.services.embedding_service import get_embedding_client
from backend.services.file_parsers.code_parser import extract_code_text
from backend.services.file_parsers.pdf_parser import PdfPageText, extract_pdf_text, stream_pdf_pages
from backend.services.file_parsers.text_parser import extract_text_content
from backend.services.text_chunking import chunk_text
from backend.services.vector_store_service import VectorSearchHit, get_vector_store

logger = logging.getLogger(__name__)

KNOWLEDGE_COLLECTION = "knowledge_units"
SOURCE_CHUNK_COLLECTION = "source_chunks"
MAX_KNOWLEDGE_EMBEDDING_BODY_CHARS = 3000


@dataclass(frozen=True)
class ChunkPageRange:
    page_start: int | None
    page_end: int | None


def build_knowledge_embedding_text(record: KnowledgeUnit) -> str:
    topic_tags = ", ".join(loads_json_list(record.topic_tags_json))
    body_text = record.body_text[:MAX_KNOWLEDGE_EMBEDDING_BODY_CHARS]
    return "\n".join(
        [
            f"Title: {record.title}",
            f"Summary: {record.summary}",
            f"Body: {body_text}",
            f"Topic Tags: {topic_tags}",
            f"Pedagogical Role: {record.pedagogical_role}",
        ]
    )


def _get_processed_source_dir(source: Source) -> Path:
    path = get_processed_storage_root() / source.source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _page_ranges_from_pages(pages: list[PdfPageText]) -> tuple[str, list[dict[str, int]]]:
    non_empty_pages = [page for page in pages if page.text]
    combined_parts: list[str] = []
    page_ranges: list[dict[str, int]] = []
    cursor = 0
    for page in non_empty_pages:
        if combined_parts:
            cursor += 2
        start = cursor
        combined_parts.append(page.text)
        cursor += len(page.text)
        page_ranges.append(
            {
                "page_number": page.page_number,
                "char_start": start,
                "char_end": cursor,
            }
        )
    return "\n\n".join(combined_parts).strip(), page_ranges


def _resolve_chunk_page_range(
    char_start: int,
    char_end: int,
    page_ranges: list[dict[str, int]],
) -> ChunkPageRange:
    if not page_ranges:
        return ChunkPageRange(page_start=None, page_end=None)

    start_page = None
    end_page = None
    for page in page_ranges:
        if start_page is None and char_start <= page["char_end"] and char_end >= page["char_start"]:
            start_page = page["page_number"]
        if char_end >= page["char_start"] and char_start <= page["char_end"]:
            end_page = page["page_number"]

    return ChunkPageRange(page_start=start_page, page_end=end_page or start_page)


def _persist_pdf_page_texts(
    source: Source,
    pages_iter,
    processed_dir: Path,
    total_pages: int,
) -> tuple[str, list[dict[str, int]]]:
    page_manifest = processed_dir / "page_texts.jsonl"
    page_manifest.write_text("", encoding="utf-8")

    pages: list[PdfPageText] = []
    for index, page in enumerate(pages_iter, start=1):
        pages.append(page)
        _append_jsonl(
            page_manifest,
            {
                "page_number": page.page_number,
                "char_count": len(page.text),
                "text": page.text,
            },
        )
        if index % 25 == 0 or index == total_pages:
            logger.info(
                "pdf extraction progress: source_id=%s processed_pages=%s/%s",
                source.source_id,
                index,
                total_pages,
            )

    combined_text, page_ranges = _page_ranges_from_pages(pages)
    _write_json(
        processed_dir / "extraction_summary.json",
        {
            "source_id": source.source_id,
            "source_type": source.source_type,
            "page_count": total_pages,
            "non_empty_page_count": len([page for page in pages if page.text]),
            "extracted_char_count": len(combined_text),
        },
    )
    return combined_text, page_ranges


def _persist_chunk_manifest(
    source: Source,
    processed_dir: Path,
    chunks,
    page_ranges: list[dict[str, int]],
) -> list[dict]:
    chunk_manifest = processed_dir / "chunk_manifest.jsonl"
    chunk_manifest.write_text("", encoding="utf-8")

    chunk_records: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        page_range = _resolve_chunk_page_range(chunk.char_start, chunk.char_end, page_ranges)
        record = {
            "chunk_id": f"src::{source.source_id}::chunk::{chunk.chunk_index}",
            "source_id": source.source_id,
            "source_type": source.source_type,
            "module_tag": source.module_tag,
            "week_tag": source.week_tag or "",
            "chunk_index": chunk.chunk_index,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "page_start": page_range.page_start,
            "page_end": page_range.page_end,
            "chunk_text": chunk.text,
        }
        _append_jsonl(chunk_manifest, record)
        chunk_records.append(record)
        if index % 50 == 0 or index == len(chunks):
            logger.info(
                "source chunking progress: source_id=%s processed_chunks=%s/%s",
                source.source_id,
                index,
                len(chunks),
            )

    return chunk_records


def _extract_source_text(source: Source) -> str | None:
    if source.source_type == "pdf":
        return extract_pdf_text(source.storage_path)
    if source.source_type == "text":
        return extract_text_content(source.storage_path)
    if source.source_type == "code":
        return extract_code_text(source.storage_path)
    return None


def index_knowledge_units(records: list[KnowledgeUnit]) -> int:
    if not records:
        return 0

    embedder = get_embedding_client()
    vector_store = get_vector_store()

    batch_size = max(1, get_embedding_batch_size())
    indexed = 0
    for batch_start in range(0, len(records), batch_size):
        batch = records[batch_start : batch_start + batch_size]
        documents = [build_knowledge_embedding_text(record) for record in batch]
        embeddings = embedder.embed_texts(documents)
        ids = [f"ku::{record.knowledge_id}::v{record.version_number}" for record in batch]
        metadatas = [
            {
                "knowledge_id": record.knowledge_id,
                "module_tag": record.module_tag,
                "week_tag": record.week_tag or "",
                "approval_status": record.approval_status,
                "pedagogical_role": record.pedagogical_role,
                "difficulty_level": record.difficulty_level or "",
                "source_type": record.source_type,
                "version_number": record.version_number,
            }
            for record in batch
        ]
        vector_store.upsert(
            collection_name=KNOWLEDGE_COLLECTION,
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        indexed += len(batch)
        logger.info(
            "semantic knowledge upsert completed: indexed=%s/%s",
            indexed,
            len(records),
        )
    logger.info("semantic index updated for knowledge units: count=%s", len(records))
    return len(records)


def index_source_chunks(source: Source) -> int:
    processed_dir = _get_processed_source_dir(source)
    page_ranges: list[dict[str, int]] = []
    extracted_text = None

    if source.source_type == "pdf":
        streamed = stream_pdf_pages(source.storage_path)
        if not streamed:
            logger.info("semantic source chunking skipped: source_id=%s type=%s", source.source_id, source.source_type)
            return 0
        total_pages, pages_iter = streamed
        logger.info(
            "pdf extraction started: source_id=%s total_pages=%s chunk_size=%s overlap=%s",
            source.source_id,
            total_pages,
            get_chunk_size(),
            get_chunk_overlap(),
        )
        extracted_text, page_ranges = _persist_pdf_page_texts(source, pages_iter, processed_dir, total_pages)
    else:
        extracted_text = _extract_source_text(source)

    if not extracted_text:
        logger.info("semantic source chunking skipped: source_id=%s type=%s", source.source_id, source.source_type)
        return 0

    chunks = chunk_text(
        text=extracted_text,
        chunk_size=get_chunk_size(),
        overlap=get_chunk_overlap(),
    )
    if not chunks:
        return 0

    chunk_records = _persist_chunk_manifest(
        source=source,
        processed_dir=processed_dir,
        chunks=chunks,
        page_ranges=page_ranges,
    )

    embedder = get_embedding_client()
    vector_store = get_vector_store()
    batch_size = max(1, min(get_source_chunk_index_batch_size(), get_embedding_batch_size()))
    total_chunks = len(chunk_records)
    indexed_chunks = 0
    for batch_start in range(0, total_chunks, batch_size):
        batch = chunk_records[batch_start : batch_start + batch_size]
        batch_end = batch_start + len(batch)
        logger.info(
            "source chunk embedding batch: source_id=%s chunks=%s-%s/%s",
            source.source_id,
            batch_start + 1,
            batch_end,
            total_chunks,
        )
        documents = [item["chunk_text"] for item in batch]
        embeddings = embedder.embed_texts(documents)
        vector_store.upsert(
            collection_name=SOURCE_CHUNK_COLLECTION,
            ids=[item["chunk_id"] for item in batch],
            documents=documents,
            embeddings=embeddings,
            metadatas=[
                {
                    "source_id": item["source_id"],
                    "module_tag": item["module_tag"],
                    "week_tag": item["week_tag"],
                    "source_type": item["source_type"],
                    "chunk_index": item["chunk_index"],
                    "char_start": item["char_start"],
                    "char_end": item["char_end"],
                    "page_start": item["page_start"],
                    "page_end": item["page_end"],
                }
                for item in batch
            ],
        )
        indexed_chunks += len(batch)
        logger.info(
            "source chunk upsert completed: source_id=%s indexed=%s/%s",
            source.source_id,
            indexed_chunks,
            total_chunks,
        )

    _write_json(
        processed_dir / "chunking_summary.json",
        {
            "source_id": source.source_id,
            "source_type": source.source_type,
            "chunk_count": total_chunks,
            "chunk_size": get_chunk_size(),
            "chunk_overlap": get_chunk_overlap(),
            "index_batch_size": batch_size,
            "extracted_char_count": len(extracted_text),
        },
    )
    logger.info("semantic index updated for source chunks: source_id=%s count=%s", source.source_id, total_chunks)
    return total_chunks


def semantic_query(collection_name: str, query_text: str, top_k: int, filters: dict[str, str | None]) -> list[VectorSearchHit]:
    normalized_filters = {key: value for key, value in filters.items() if value is not None}
    query_embedding = get_embedding_client().embed_texts([query_text])[0]
    return get_vector_store().query(
        collection_name=collection_name,
        query_embedding=query_embedding,
        top_k=top_k,
        filters=normalized_filters,
    )
