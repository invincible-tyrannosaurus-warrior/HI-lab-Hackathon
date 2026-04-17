from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.common import CompileKnowledgeResponse
from backend.schemas.knowledge_unit import (
    CompileKnowledgeRequest,
    ContextBundleResponse,
    KnowledgeUnitResponse,
    KnowledgeUnitSummary,
)
from backend.services.knowledge_service import compile_knowledge, get_knowledge_or_404, to_knowledge_response
from backend.services.retrieval_service import build_context_bundle, search_knowledge

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/compile", response_model=CompileKnowledgeResponse)
def compile_knowledge_endpoint(payload: CompileKnowledgeRequest, db: Session = Depends(get_db)):
    return compile_knowledge(db, payload)


@router.get("/search", response_model=list[KnowledgeUnitSummary])
def search_knowledge_endpoint(
    module: str | None = Query(None),
    week: str | None = Query(None),
    topic: str | None = Query(None),
    approval_status: str | None = Query(None),
    pedagogical_role: str | None = Query(None),
    difficulty_level: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return search_knowledge(
        db=db,
        module=module,
        week=week,
        topic=topic,
        approval_status=approval_status,
        pedagogical_role=pedagogical_role,
        difficulty_level=difficulty_level,
        q=q,
    )


@router.get("/context-bundle", response_model=ContextBundleResponse)
def get_context_bundle(
    generation_target: str,
    module: str | None = Query(None),
    week: str | None = Query(None),
    topic: str | None = Query(None),
    difficulty_level: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return build_context_bundle(
        db=db,
        module=module,
        week=week,
        topic=topic,
        generation_target=generation_target,
        difficulty_level=difficulty_level,
    )


@router.get("/{knowledge_id}", response_model=KnowledgeUnitResponse)
def get_knowledge(knowledge_id: str, db: Session = Depends(get_db)):
    return to_knowledge_response(get_knowledge_or_404(db, knowledge_id))
