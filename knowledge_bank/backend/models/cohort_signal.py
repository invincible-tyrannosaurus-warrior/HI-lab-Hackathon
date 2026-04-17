from __future__ import annotations

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CohortSignal(Base):
    __tablename__ = "cohort_signals"

    signal_id: Mapped[str] = mapped_column(String, primary_key=True)
    tested_deck_id: Mapped[str] = mapped_column(String, nullable=False)
    related_knowledge_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    weak_topics_json: Mapped[str] = mapped_column(Text, nullable=False)
    repeated_confusion_points_json: Mapped[str] = mapped_column(Text, nullable=False)
    misconception_clusters_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
