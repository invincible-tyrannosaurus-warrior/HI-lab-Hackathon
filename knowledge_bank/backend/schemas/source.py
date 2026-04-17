from __future__ import annotations

from datetime import datetime

from backend.schemas.common import APIModel


class SourceResponse(APIModel):
    source_id: str
    filename: str
    source_type: str
    module_tag: str
    week_tag: str | None = None
    uploader: str
    hash: str
    storage_path: str
    created_at: datetime
