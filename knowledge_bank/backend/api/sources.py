from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.source import SourceResponse
from backend.services.source_service import get_source_or_404, list_sources, register_source, to_source_response

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def upload_source(
    file: UploadFile = File(...),
    module_tag: str = Form(...),
    week_tag: str | None = Form(None),
    uploader: str = Form("human_or_agent"),
    source_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    return register_source(
        db=db,
        upload_file=file,
        module_tag=module_tag,
        week_tag=week_tag,
        uploader=uploader,
        provided_source_type=source_type,
    )


@router.get("", response_model=list[SourceResponse])
def get_sources(
    module: str | None = None,
    week: str | None = None,
    source_type: str | None = None,
    db: Session = Depends(get_db),
):
    return list_sources(db=db, module=module, week=week, source_type=source_type)


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: str, db: Session = Depends(get_db)):
    return to_source_response(get_source_or_404(db, source_id))
