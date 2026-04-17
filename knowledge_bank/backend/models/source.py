from __future__ import annotations

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    module_tag: Mapped[str] = mapped_column(String, nullable=False)
    week_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    uploader: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
