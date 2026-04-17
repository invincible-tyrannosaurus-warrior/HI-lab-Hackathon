from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.knowledge_unit import (
    ApprovalRequest,
    ApprovalResponse,
    BulkApprovalRequest,
    BulkApprovalResponse,
)
from backend.services.approval_service import approve_knowledge, approve_knowledge_bulk

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/bulk", response_model=BulkApprovalResponse)
def approve_knowledge_bulk_endpoint(
    payload: BulkApprovalRequest,
    db: Session = Depends(get_db),
):
    return approve_knowledge_bulk(db, payload)


@router.post("/{knowledge_id}", response_model=ApprovalResponse)
def approve_knowledge_endpoint(
    knowledge_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
):
    return approve_knowledge(db, knowledge_id, payload)
