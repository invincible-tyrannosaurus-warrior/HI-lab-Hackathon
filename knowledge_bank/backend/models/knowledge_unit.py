from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    knowledge_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    module_tag: Mapped[str] = mapped_column(String, nullable=False)
    week_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    topic_tags_json: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty_level: Mapped[str | None] = mapped_column(String, nullable=True)
    pedagogical_role: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_ref_json: Mapped[str] = mapped_column(Text, nullable=False)
    approval_status: Mapped[str] = mapped_column(String, nullable=False)
    prerequisite_links_json: Mapped[str] = mapped_column(Text, nullable=False)
    learning_outcome_links_json: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
