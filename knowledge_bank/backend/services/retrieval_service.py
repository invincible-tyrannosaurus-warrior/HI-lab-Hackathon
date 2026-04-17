from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models.knowledge_unit import KnowledgeUnit
from backend.models.source import Source
from backend.schemas.common import GraphEdge, GraphNode, GraphResponse, loads_json_list, parse_topic_scope
from backend.schemas.knowledge_unit import (
    ContextBundleItem,
    ContextBundleResponse,
    KnowledgeUnitSummary,
    RetrievalTrace,
    SupportingSourceChunk,
)
from backend.schemas.source import SourceResponse
from backend.services.semantic_index_service import KNOWLEDGE_COLLECTION, SOURCE_CHUNK_COLLECTION, semantic_query
from backend.services.topic_matching import best_topic_scope_score, matches_topic_scope, normalize_topic_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicMatchedRecord:
    record: KnowledgeUnit
    topic_score: int | None


def _topic_candidate_values(record: KnowledgeUnit) -> list[str]:
    return [record.title, *loads_json_list(record.topic_tags_json)]


def _topic_match_score(record: KnowledgeUnit, topic_scope: list[str]) -> int | None:
    title_score = best_topic_scope_score(topic_scope, [record.title])
    tag_score = best_topic_scope_score(topic_scope, loads_json_list(record.topic_tags_json))

    scores: list[int] = []
    if title_score is not None:
        scores.append(title_score)
    if tag_score is not None:
        scores.append(tag_score + 3)
    if not scores:
        return None
    return min(scores)


def _matches_topic(record: KnowledgeUnit, topic_scope: list[str]) -> bool:
    return matches_topic_scope(topic_scope, _topic_candidate_values(record))


def _matches_text_query(record: KnowledgeUnit, query_text: str | None) -> bool:
    if not query_text:
        return True
    haystack = normalize_topic_text(" ".join([record.title, record.summary, record.body_text]))
    return normalize_topic_text(query_text) in haystack


def _to_summary(record: KnowledgeUnit) -> KnowledgeUnitSummary:
    return KnowledgeUnitSummary(
        knowledge_id=record.knowledge_id,
        title=record.title,
        summary=record.summary,
        module_tag=record.module_tag,
        week_tag=record.week_tag,
        topic_tags=loads_json_list(record.topic_tags_json),
        pedagogical_role=record.pedagogical_role,
        approval_status=record.approval_status,
        source_ref=loads_json_list(record.source_ref_json),
        version_number=record.version_number,
        updated_at=record.updated_at,
    )


def search_knowledge(
    db: Session,
    module: str | None,
    week: str | None,
    topic: str | None,
    approval_status: str | None,
    pedagogical_role: str | None,
    difficulty_level: str | None,
    q: str | None,
) -> list[KnowledgeUnitSummary]:
    # Explicit default: when approval_status is omitted, search returns both draft and approved records.
    query = db.query(KnowledgeUnit)
    if module:
        query = query.filter(KnowledgeUnit.module_tag == module)
    if week:
        query = query.filter(KnowledgeUnit.week_tag == week)
    if approval_status:
        query = query.filter(KnowledgeUnit.approval_status == approval_status)
    if pedagogical_role:
        query = query.filter(KnowledgeUnit.pedagogical_role == pedagogical_role)
    if difficulty_level:
        query = query.filter(KnowledgeUnit.difficulty_level == difficulty_level)

    records = query.all()
    topic_scope = parse_topic_scope(topic)
    matched_records = [
        TopicMatchedRecord(record=record, topic_score=_topic_match_score(record, topic_scope))
        for record in records
        if _matches_topic(record, topic_scope)
    ]
    matched_records = [
        item for item in matched_records if _matches_text_query(item.record, q)
    ]
    matched_records.sort(
        key=lambda item: (
            item.topic_score if item.topic_score is not None else 9999,
            -item.record.updated_at.timestamp(),
            item.record.knowledge_id,
        )
    )
    return [_to_summary(item.record) for item in matched_records]


def build_context_bundle(
    db: Session,
    module: str | None,
    week: str | None,
    topic: str | None,
    generation_target: str,
    difficulty_level: str | None,
) -> ContextBundleResponse:
    query = db.query(KnowledgeUnit).filter(KnowledgeUnit.approval_status == "approved")
    if module:
        query = query.filter(KnowledgeUnit.module_tag == module)
    if week:
        query = query.filter(KnowledgeUnit.week_tag == week)
    if difficulty_level:
        query = query.filter(KnowledgeUnit.difficulty_level == difficulty_level)

    records = query.all()
    topic_scope = parse_topic_scope(topic)
    metadata_topic_matches = [
        TopicMatchedRecord(record=record, topic_score=_topic_match_score(record, topic_scope))
        for record in records
        if _matches_topic(record, topic_scope)
    ]

    role_priority = {
        "concept": 0,
        "example": 1,
        "caution": 2,
        "prerequisite": 3,
    }

    semantic_query_text = None
    vector_collections: list[str] = []
    trace_notes: list[str] = []
    semantic_knowledge_rank: dict[str, int] = {}
    if topic_scope:
        semantic_query_text = " | ".join(
            item
            for item in [
                module or "",
                week or "",
                ", ".join(topic_scope),
                generation_target,
            ]
            if item
        )
        try:
            knowledge_hits = semantic_query(
                collection_name=KNOWLEDGE_COLLECTION,
                query_text=semantic_query_text,
                top_k=max(8, len(topic_scope) * 4),
                filters={
                    "module_tag": module,
                    "week_tag": week,
                    "approval_status": "approved",
                    "difficulty_level": difficulty_level,
                },
            )
            vector_collections.append(KNOWLEDGE_COLLECTION)
            semantic_knowledge_rank = {
                hit.metadata.get("knowledge_id", ""): index for index, hit in enumerate(knowledge_hits)
            }
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("semantic knowledge lookup failed: %s", exc)
            trace_notes.append(f"knowledge semantic lookup failed: {exc}")

    selected_by_id = {item.record.knowledge_id: item.record for item in metadata_topic_matches}
    metadata_topic_rank = {
        item.record.knowledge_id: item.topic_score if item.topic_score is not None else 9999
        for item in metadata_topic_matches
    }
    if semantic_knowledge_rank:
        for record in records:
            if record.knowledge_id in semantic_knowledge_rank:
                selected_by_id.setdefault(record.knowledge_id, record)

    selected_records = list(selected_by_id.values()) if topic_scope else records
    selected_records.sort(
        key=lambda record: (
            metadata_topic_rank.get(record.knowledge_id, 9999),
            role_priority.get(record.pedagogical_role, 99),
            semantic_knowledge_rank.get(record.knowledge_id, 9999),
            -record.updated_at.timestamp(),
            record.knowledge_id,
        )
    )

    bundle = [
        ContextBundleItem(
            knowledge_id=record.knowledge_id,
            title=record.title,
            summary=record.summary,
            body_text=record.body_text,
            pedagogical_role=record.pedagogical_role,
            topic_tags=loads_json_list(record.topic_tags_json),
            prerequisite_links=loads_json_list(record.prerequisite_links_json),
            source_ref=loads_json_list(record.source_ref_json),
            approval_status=record.approval_status,
            version_number=record.version_number,
        )
        for record in selected_records
    ]

    source_ids_from_bundle = sorted(
        {
            source_id
            for item in bundle
            for source_id in item.source_ref
        }
    )
    supporting_source_chunks: list[SupportingSourceChunk] = []
    supporting_chunk_ids: list[str] = []
    if source_ids_from_bundle and semantic_query_text:
        try:
            chunk_hits = semantic_query(
                collection_name=SOURCE_CHUNK_COLLECTION,
                query_text=semantic_query_text,
                top_k=24,
                filters={
                    "module_tag": module,
                    "week_tag": week,
                },
            )
            vector_collections.append(SOURCE_CHUNK_COLLECTION)
            filtered_hits = [
                hit for hit in chunk_hits if hit.metadata.get("source_id") in source_ids_from_bundle
            ]
            deduped_hits = []
            seen_chunk_ids = set()
            for hit in filtered_hits:
                if hit.id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(hit.id)
                deduped_hits.append(hit)
            supporting_source_chunks = [
                SupportingSourceChunk(
                    chunk_id=hit.id,
                    source_id=str(hit.metadata.get("source_id", "")),
                    source_type=str(hit.metadata.get("source_type", "")),
                    chunk_index=int(hit.metadata.get("chunk_index", 0)),
                    char_start=int(hit.metadata.get("char_start", 0)),
                    char_end=int(hit.metadata.get("char_end", 0)),
                    page_start=int(hit.metadata["page_start"]) if hit.metadata.get("page_start") is not None else None,
                    page_end=int(hit.metadata["page_end"]) if hit.metadata.get("page_end") is not None else None,
                    chunk_text=hit.document,
                    similarity_score=round(hit.score, 6),
                )
                for hit in deduped_hits[:8]
            ]
            supporting_chunk_ids = [item.chunk_id for item in supporting_source_chunks]
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("semantic source chunk lookup failed: %s", exc)
            trace_notes.append(f"source chunk semantic lookup failed: {exc}")

    source_refs = (
        db.query(Source)
        .filter(Source.source_id.in_(source_ids_from_bundle))
        .order_by(Source.created_at.asc(), Source.source_id.asc())
        .all()
        if source_ids_from_bundle
        else []
    )
    source_registry_refs = [SourceResponse.model_validate(source) for source in source_refs]

    trace = RetrievalTrace(
        metadata_filters={
            "module_tag": module,
            "week_tag": week,
            "topic_scope": topic_scope,
            "approval_status": "approved",
            "difficulty_level": difficulty_level,
        },
        vector_search_used=bool(vector_collections),
        vector_collections_queried=vector_collections,
        semantic_query_text=semantic_query_text,
        approved_knowledge_ids=[item.knowledge_id for item in bundle],
        supporting_chunk_ids=supporting_chunk_ids,
        notes=trace_notes,
    )
    logger.info(
        "context bundle request served: approved_count=%s source_chunks=%s",
        len(bundle),
        len(supporting_source_chunks),
    )
    return ContextBundleResponse(
        module_tag=module,
        week_tag=week,
        topic_scope=topic_scope,
        generation_target=generation_target,
        approved_context_bundle=bundle,
        supporting_source_chunks=supporting_source_chunks,
        source_registry_refs=source_registry_refs,
        retrieval_trace=trace,
    )


def build_graph(db: Session) -> GraphResponse:
    source_records = db.query(Source).order_by(Source.created_at.asc(), Source.source_id.asc()).all()
    knowledge_records = db.query(KnowledgeUnit).order_by(KnowledgeUnit.updated_at.asc(), KnowledgeUnit.knowledge_id.asc()).all()

    nodes = [
        GraphNode(id=source.source_id, label=source.filename, type="source")
        for source in source_records
    ]
    nodes.extend(
        GraphNode(
            id=knowledge.knowledge_id,
            label=knowledge.title,
            type="knowledge_unit",
            status=knowledge.approval_status,
        )
        for knowledge in knowledge_records
    )

    edges: list[GraphEdge] = []
    known_ids = {record.knowledge_id for record in knowledge_records}
    for knowledge in knowledge_records:
        for source_id in loads_json_list(knowledge.source_ref_json):
            edges.append(GraphEdge(source=source_id, target=knowledge.knowledge_id, type="derived_from"))
        for prerequisite in loads_json_list(knowledge.prerequisite_links_json):
            if prerequisite in known_ids:
                edges.append(
                    GraphEdge(source=prerequisite, target=knowledge.knowledge_id, type="prerequisite")
                )

    return GraphResponse(nodes=nodes, edges=edges)
