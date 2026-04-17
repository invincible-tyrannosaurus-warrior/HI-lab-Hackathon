from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.signal import CohortSignalCreate, CohortSignalStoredResponse
from backend.services.signal_service import store_cohort_signal

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/cohort", response_model=CohortSignalStoredResponse, status_code=status.HTTP_201_CREATED)
def store_signal(payload: CohortSignalCreate, db: Session = Depends(get_db)):
    return store_cohort_signal(db, payload)
