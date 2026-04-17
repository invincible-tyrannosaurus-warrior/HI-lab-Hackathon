from __future__ import annotations

from pydantic import Field

from backend.schemas.common import APIModel


class CohortSignalCreate(APIModel):
    tested_deck_id: str
    related_knowledge_ids: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    repeated_confusion_points: list[str] = Field(default_factory=list)
    misconception_clusters: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class CohortSignalStoredResponse(APIModel):
    signal_id: str
    status: str
