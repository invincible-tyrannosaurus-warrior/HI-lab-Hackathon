from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.knowledge_unit import KnowledgeUnit
from backend.models.source import Source
from backend.schemas.common import KnowledgeSummaryResponse


def build_summary(db: Session) -> KnowledgeSummaryResponse:
    registered_sources = db.query(func.count(Source.source_id)).scalar() or 0
    draft_units = (
        db.query(func.count(KnowledgeUnit.knowledge_id))
        .filter(KnowledgeUnit.approval_status == "draft")
        .scalar()
        or 0
    )
    approved_units = (
        db.query(func.count(KnowledgeUnit.knowledge_id))
        .filter(KnowledgeUnit.approval_status == "approved")
        .scalar()
        or 0
    )
    latest_source_at = db.query(func.max(Source.created_at)).scalar()
    latest_knowledge_at = db.query(func.max(KnowledgeUnit.updated_at)).scalar()
    latest_update_at = max(
        [value for value in [latest_source_at, latest_knowledge_at] if value is not None],
        default=None,
    )
    return KnowledgeSummaryResponse(
        registered_sources=registered_sources,
        draft_units=draft_units,
        approved_units=approved_units,
        latest_update_at=latest_update_at,
    )
