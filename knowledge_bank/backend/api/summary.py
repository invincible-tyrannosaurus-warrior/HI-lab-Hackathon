from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.common import GraphResponse, KnowledgeSummaryResponse
from backend.services.retrieval_service import build_graph
from backend.services.summary_service import build_summary

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/summary", response_model=KnowledgeSummaryResponse)
def get_summary(db: Session = Depends(get_db)):
    return build_summary(db)


@router.get("/graph", response_model=GraphResponse)
def get_graph(db: Session = Depends(get_db)):
    return build_graph(db)
