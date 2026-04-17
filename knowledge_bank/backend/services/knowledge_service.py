from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.config import get_processed_storage_root
from backend.models.knowledge_unit import KnowledgeUnit
from backend.schemas.common import CompileKnowledgeResponse, dumps_json_list, generate_prefixed_id, utc_now
from backend.schemas.knowledge_unit import CompileKnowledgeRequest, KnowledgeUnitResponse
from backend.services.auto_compile_service import GeneratedCompiledUnit, build_generated_compiled_units
from backend.services.semantic_index_service import index_knowledge_units, index_source_chunks
from backend.services.source_service import get_source_or_404, preview_source_content

logger = logging.getLogger(__name__)


def to_knowledge_response(record: KnowledgeUnit) -> KnowledgeUnitResponse:
    from backend.schemas.common import loads_json_list

    return KnowledgeUnitResponse(
        knowledge_id=record.knowledge_id,
        title=record.title,
        summary=record.summary,
        body_text=record.body_text,
        module_tag=record.module_tag,
        week_tag=record.week_tag,
        topic_tags=loads_json_list(record.topic_tags_json),
        difficulty_level=record.difficulty_level,
        pedagogical_role=record.pedagogical_role,
        source_type=record.source_type,
        source_ref=loads_json_list(record.source_ref_json),
        approval_status=record.approval_status,
        prerequisite_links=loads_json_list(record.prerequisite_links_json),
        learning_outcome_links=loads_json_list(record.learning_outcome_links_json),
        version_number=record.version_number,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def get_knowledge_or_404(db: Session, knowledge_id: str) -> KnowledgeUnit:
    knowledge = db.get(KnowledgeUnit, knowledge_id)
    if knowledge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge unit not found")
    return knowledge


def _list_existing_source_units(db: Session, source_id: str) -> list[KnowledgeUnit]:
    return (
        db.query(KnowledgeUnit)
        .filter(KnowledgeUnit.source_ref_json.like(f'%"{source_id}"%'))
        .order_by(KnowledgeUnit.created_at.asc(), KnowledgeUnit.knowledge_id.asc())
        .all()
    )


def _has_existing_source_chunk_artifacts(source) -> bool:
    processed_dir = get_processed_storage_root() / source.source_id
    return (processed_dir / "chunk_manifest.jsonl").exists() and (processed_dir / "chunking_summary.json").exists()


def _store_generated_units(
    db: Session,
    source,
    generated_units: list[GeneratedCompiledUnit],
) -> tuple[list[KnowledgeUnit], list[str]]:
    now = utc_now()
    generated_id_map = {unit.key: generate_prefixed_id("kb") for unit in generated_units}
    created_records: list[KnowledgeUnit] = []
    created_ids: list[str] = []

    for item in generated_units:
        payload = item.payload
        prerequisite_links = list(payload.prerequisite_links)
        prerequisite_links.extend(
            generated_id_map[key]
            for key in item.prerequisite_keys
            if key in generated_id_map
        )
        prerequisite_links = list(dict.fromkeys(prerequisite_links))

        record = KnowledgeUnit(
            knowledge_id=generated_id_map[item.key],
            title=payload.title,
            summary=payload.summary,
            body_text=payload.body_text,
            module_tag=payload.module_tag or source.module_tag,
            week_tag=payload.week_tag if payload.week_tag is not None else source.week_tag,
            topic_tags_json=dumps_json_list(payload.topic_tags),
            difficulty_level=payload.difficulty_level,
            pedagogical_role=payload.pedagogical_role,
            source_type=payload.source_type or source.source_type,
            source_ref_json=dumps_json_list(payload.source_ref or [source.source_id]),
            approval_status="draft",
            prerequisite_links_json=dumps_json_list(prerequisite_links),
            learning_outcome_links_json=dumps_json_list(payload.learning_outcome_links),
            version_number=1,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        created_ids.append(record.knowledge_id)
        created_records.append(record)

    db.commit()
    for record in created_records:
        db.refresh(record)
    return created_records, created_ids


def compile_knowledge(db: Session, payload: CompileKnowledgeRequest) -> CompileKnowledgeResponse:
    source = get_source_or_404(db, payload.source_id)
    job_id = f"job_compile_{generate_prefixed_id('run').split('_', 1)[1]}"

    if not payload.compiled_units:
        generated_units = build_generated_compiled_units(source)
        if generated_units:
            existing_titles = {record.title for record in _list_existing_source_units(db, source.source_id)}
            filtered_units = [item for item in generated_units if item.payload.title not in existing_titles]
            if not filtered_units:
                parser_preview = preview_source_content(source)
                existing_records = _list_existing_source_units(db, source.source_id)
                message = (
                    "Automatic compile found generated units, but all matching titles already exist for this source. "
                    f"Parser route: {parser_preview['parser']} ({parser_preview['status']})."
                )
                return CompileKnowledgeResponse(
                    job_id=job_id,
                    created_knowledge_ids=[record.knowledge_id for record in existing_records],
                    status="existing",
                    message=message,
                )
            created_records, created_ids = _store_generated_units(db, source, filtered_units)
            logger.info(
                "knowledge auto compile write success: source_id=%s created=%s",
                source.source_id,
                len(created_ids),
            )
        else:
            parser_preview = preview_source_content(source)
            chunk_count = 0
            indexing_note = "Semantic indexing skipped."
            try:
                chunk_count = index_source_chunks(source)
                indexing_note = f"Semantic source chunk indexing completed with {chunk_count} chunks."
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("semantic indexing failed for source_id=%s error=%s", source.source_id, exc)
                indexing_note = f"Semantic indexing failed: {exc}"
            message = (
                "Automatic compile could not derive knowledge units from the available source content. "
                f"Source is registered and ready for explicit compile handoff. "
                f"Parser route: {parser_preview['parser']} ({parser_preview['status']}). "
                f"{indexing_note}"
            )
            logger.info("knowledge compile stub returned: source_id=%s", source.source_id)
            return CompileKnowledgeResponse(
                job_id=job_id,
                created_knowledge_ids=[],
                status="stub",
                message=message,
            )
    else:
        manual_units = [
            GeneratedCompiledUnit(
                key=f"manual_{index}",
                payload=unit,
                prerequisite_keys=[],
            )
            for index, unit in enumerate(payload.compiled_units, start=1)
        ]
        created_records, created_ids = _store_generated_units(db, source, manual_units)

    semantic_notes: list[str] = []
    try:
        indexed_units = index_knowledge_units(created_records)
        semantic_notes.append(f"indexed {indexed_units} knowledge units")
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("knowledge unit indexing failed: %s", exc)
        semantic_notes.append(f"knowledge unit indexing failed: {exc}")

    try:
        if _has_existing_source_chunk_artifacts(source):
            semantic_notes.append("reused existing source chunk artifacts")
        else:
            chunk_count = index_source_chunks(source)
            semantic_notes.append(f"indexed {chunk_count} source chunks")
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("source chunk indexing failed for source_id=%s error=%s", source.source_id, exc)
        semantic_notes.append(f"source chunk indexing failed: {exc}")

    logger.info(
        "knowledge compile write success: source_id=%s created=%s",
        source.source_id,
        len(created_ids),
    )
    return CompileKnowledgeResponse(
        job_id=job_id,
        created_knowledge_ids=created_ids,
        status="stored",
        message="; ".join(semantic_notes) if semantic_notes else None,
    )
