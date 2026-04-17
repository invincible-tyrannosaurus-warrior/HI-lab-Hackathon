from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.models.source import Source
from backend.schemas.common import generate_prefixed_id, utc_now
from backend.schemas.source import SourceResponse
from backend.services.file_parsers.code_parser import parse_code
from backend.services.file_parsers.image_parser import parse_image
from backend.services.file_parsers.pdf_parser import parse_pdf
from backend.services.file_parsers.text_parser import parse_text

logger = logging.getLogger(__name__)

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
CODE_EXTENSIONS = {".py", ".ipynb", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv"}


def get_storage_root() -> Path:
    configured_root = os.getenv("KB_STORAGE_ROOT")
    if configured_root:
        path = Path(configured_root)
    else:
        path = Path(__file__).resolve().parents[1] / "storage" / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(filename: str) -> str:
    clean_name = Path(filename or "upload.bin").name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", clean_name)


def infer_source_type(filename: str, provided_source_type: str | None = None) -> str:
    normalized = (provided_source_type or "").strip().lower()
    if normalized in {"pdf"}:
        return "pdf"
    if normalized in {"image", "png", "jpg", "jpeg", "webp"}:
        return "image"
    if normalized in {"code", "py", "ipynb", "js", "ts", "java", "cpp", "c", "go", "rs"}:
        return "code"
    if normalized in {"text", "txt", "md", "json", "csv"}:
        return "text"

    extension = Path(filename).suffix.lower()
    if extension in PDF_EXTENSIONS:
        return "pdf"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in CODE_EXTENSIONS:
        return "code"
    if extension in TEXT_EXTENSIONS:
        return "text"
    return "unknown"


def get_parser_for_source_type(source_type: str):
    return {
        "pdf": parse_pdf,
        "image": parse_image,
        "code": parse_code,
        "text": parse_text,
    }.get(source_type)


def preview_source_content(source: Source) -> dict[str, str | None]:
    parser = get_parser_for_source_type(source.source_type)
    if parser is None:
        return {
            "parser": "none",
            "status": "fallback",
            "message": "No parser is registered for this source type yet.",
            "extracted_text_preview": None,
        }
    return parser(source.storage_path)


def save_upload_file(upload_file: UploadFile, destination: Path) -> str:
    hasher = hashlib.sha256()
    with destination.open("wb") as output_file:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            output_file.write(chunk)
    upload_file.file.seek(0)
    return f"sha256_{hasher.hexdigest()}"


def to_source_response(source: Source) -> SourceResponse:
    return SourceResponse.model_validate(source)


def register_source(
    db: Session,
    upload_file: UploadFile,
    module_tag: str,
    week_tag: str | None,
    uploader: str,
    provided_source_type: str | None = None,
) -> SourceResponse:
    filename = sanitize_filename(upload_file.filename or "upload.bin")
    source_id = generate_prefixed_id("src")
    source_type = infer_source_type(filename, provided_source_type)
    destination = get_storage_root() / f"{source_id}_{filename}"
    file_hash = save_upload_file(upload_file, destination)

    source = Source(
        source_id=source_id,
        filename=filename,
        source_type=source_type,
        module_tag=module_tag,
        week_tag=week_tag,
        uploader=uploader,
        hash=file_hash,
        storage_path=str(destination),
        created_at=utc_now(),
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info("source upload success: source_id=%s type=%s", source.source_id, source.source_type)
    return to_source_response(source)


def list_sources(
    db: Session,
    module: str | None = None,
    week: str | None = None,
    source_type: str | None = None,
) -> list[SourceResponse]:
    query = db.query(Source)
    if module:
        query = query.filter(Source.module_tag == module)
    if week:
        query = query.filter(Source.week_tag == week)
    if source_type:
        query = query.filter(Source.source_type == infer_source_type("placeholder", source_type))

    sources = query.order_by(Source.created_at.desc(), Source.source_id.asc()).all()
    return [to_source_response(source) for source in sources]


def get_source_or_404(db: Session, source_id: str) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source
