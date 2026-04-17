from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.schemas.common import loads_json_list, utc_now
from backend.schemas.common import parse_topic_scope
from backend.schemas.knowledge_unit import (
    ApprovalRequest,
    ApprovalResponse,
    BulkApprovalRequest,
    BulkApprovalResponse,
)
from backend.models.knowledge_unit import KnowledgeUnit
from backend.services.semantic_index_service import index_knowledge_units
from backend.services.knowledge_service import get_knowledge_or_404
from backend.services.topic_matching import matches_topic_scope

logger = logging.getLogger(__name__)


def _approve_records(db: Session, records: list[KnowledgeUnit]) -> None:
    now = utc_now()
    for record in records:
        record.approval_status = "approved"
        record.updated_at = now
        db.add(record)
    db.commit()
    for record in records:
        db.refresh(record)


def _filter_bulk_records(db: Session, payload: BulkApprovalRequest) -> list[KnowledgeUnit]:
    query = db.query(KnowledgeUnit).filter(KnowledgeUnit.approval_status == "draft")
    if payload.module:
        query = query.filter(KnowledgeUnit.module_tag == payload.module)
    if payload.week:
        query = query.filter(KnowledgeUnit.week_tag == payload.week)
    if payload.pedagogical_role:
        query = query.filter(KnowledgeUnit.pedagogical_role == payload.pedagogical_role)
    if payload.difficulty_level:
        query = query.filter(KnowledgeUnit.difficulty_level == payload.difficulty_level)

    records = query.order_by(KnowledgeUnit.updated_at.desc(), KnowledgeUnit.knowledge_id.asc()).all()
    requested_ids = set(payload.knowledge_ids)
    if requested_ids:
        records = [record for record in records if record.knowledge_id in requested_ids]

    topic_scope = parse_topic_scope(payload.topic)
    if topic_scope:
        records = [
            record
            for record in records
            if matches_topic_scope(topic_scope, [record.title, *loads_json_list(record.topic_tags_json)])
        ]

    if payload.limit is not None:
        records = records[: max(0, payload.limit)]
    return records


def approve_knowledge(db: Session, knowledge_id: str, payload: ApprovalRequest) -> ApprovalResponse:
    knowledge = get_knowledge_or_404(db, knowledge_id)

    if payload.target_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft -> approved transitions are supported in the MVP",
        )
    if knowledge.approval_status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft knowledge units can be approved",
        )

    _approve_records(db, [knowledge])
    try:
        index_knowledge_units([knowledge])
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("knowledge reindex failed after approval knowledge_id=%s error=%s", knowledge_id, exc)
    logger.info("approval update success: knowledge_id=%s reviewer=%s", knowledge_id, payload.reviewer)
    return ApprovalResponse(
        knowledge_id=knowledge.knowledge_id,
        new_status=knowledge.approval_status,
        updated_at=knowledge.updated_at,
    )


def approve_knowledge_bulk(db: Session, payload: BulkApprovalRequest) -> BulkApprovalResponse:
    if payload.target_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft -> approved transitions are supported in the MVP",
        )

    records = _filter_bulk_records(db, payload)
    approved_ids = [record.knowledge_id for record in records]
    skipped_ids: list[str] = []
    if payload.knowledge_ids:
        skipped_ids = [knowledge_id for knowledge_id in payload.knowledge_ids if knowledge_id not in approved_ids]

    if records:
        _approve_records(db, records)
        try:
            index_knowledge_units(records)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("knowledge bulk reindex failed after approval error=%s", exc)

    logger.info(
        "bulk approval update success: reviewer=%s approved=%s",
        payload.reviewer,
        len(approved_ids),
    )
    updated_at = records[0].updated_at if records else utc_now()
    return BulkApprovalResponse(
        approved_knowledge_ids=approved_ids,
        skipped_knowledge_ids=skipped_ids,
        approved_count=len(approved_ids),
        updated_at=updated_at,
    )
