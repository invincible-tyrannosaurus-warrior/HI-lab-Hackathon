from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backend.schemas.common import APIModel, ApprovalStatus
from backend.schemas.source import SourceResponse


class CompiledKnowledgeUnitInput(APIModel):
    title: str
    summary: str
    body_text: str
    module_tag: str | None = None
    week_tag: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    difficulty_level: str | None = None
    pedagogical_role: str
    source_type: str | None = None
    source_ref: list[str] | None = None
    approval_status: ApprovalStatus | None = None
    prerequisite_links: list[str] = Field(default_factory=list)
    learning_outcome_links: list[str] = Field(default_factory=list)


class CompileKnowledgeRequest(APIModel):
    source_id: str
    compiled_units: list[CompiledKnowledgeUnitInput] | None = None


class KnowledgeUnitSummary(APIModel):
    knowledge_id: str
    title: str
    summary: str
    module_tag: str
    week_tag: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    pedagogical_role: str
    approval_status: ApprovalStatus
    source_ref: list[str] = Field(default_factory=list)
    version_number: int
    updated_at: datetime


class KnowledgeUnitResponse(KnowledgeUnitSummary):
    body_text: str
    difficulty_level: str | None = None
    source_type: str
    prerequisite_links: list[str] = Field(default_factory=list)
    learning_outcome_links: list[str] = Field(default_factory=list)
    created_at: datetime


class ApprovalRequest(APIModel):
    target_status: ApprovalStatus
    reviewer: str
    decision_reason: str


class ApprovalResponse(APIModel):
    knowledge_id: str
    new_status: ApprovalStatus
    updated_at: datetime


class BulkApprovalRequest(APIModel):
    target_status: ApprovalStatus
    reviewer: str
    decision_reason: str
    knowledge_ids: list[str] = Field(default_factory=list)
    module: str | None = None
    week: str | None = None
    topic: str | None = None
    pedagogical_role: str | None = None
    difficulty_level: str | None = None
    limit: int | None = None


class BulkApprovalResponse(APIModel):
    approved_knowledge_ids: list[str] = Field(default_factory=list)
    skipped_knowledge_ids: list[str] = Field(default_factory=list)
    approved_count: int
    updated_at: datetime


class ContextBundleItem(APIModel):
    knowledge_id: str
    title: str
    summary: str
    body_text: str
    pedagogical_role: str
    topic_tags: list[str] = Field(default_factory=list)
    prerequisite_links: list[str] = Field(default_factory=list)
    source_ref: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus
    version_number: int


class ContextBundleResponse(APIModel):
    module_tag: str | None = None
    week_tag: str | None = None
    topic_scope: list[str] = Field(default_factory=list)
    generation_target: str
    approved_context_bundle: list[ContextBundleItem] = Field(default_factory=list)
    supporting_source_chunks: list["SupportingSourceChunk"] = Field(default_factory=list)
    source_registry_refs: list[SourceResponse] = Field(default_factory=list)
    retrieval_trace: "RetrievalTrace"


class SupportingSourceChunk(APIModel):
    chunk_id: str
    source_id: str
    source_type: str
    chunk_index: int
    char_start: int
    char_end: int
    page_start: int | None = None
    page_end: int | None = None
    chunk_text: str
    similarity_score: float


class RetrievalTrace(APIModel):
    metadata_filters: dict[str, str | list[str] | None]
    vector_search_used: bool
    vector_collections_queried: list[str] = Field(default_factory=list)
    semantic_query_text: str | None = None
    approved_knowledge_ids: list[str] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


ContextBundleResponse.model_rebuild()
