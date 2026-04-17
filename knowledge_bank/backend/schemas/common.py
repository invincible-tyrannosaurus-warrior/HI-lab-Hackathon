from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ApprovalStatus = Literal["draft", "approved"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_prefixed_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def dumps_json_list(values: list[str] | None) -> str:
    return json.dumps(values or [], ensure_ascii=False)


def loads_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_topic_scope(topic_query: str | None) -> list[str]:
    if not topic_query:
        return []
    return [item.strip() for item in topic_query.split(",") if item.strip()]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompileKnowledgeResponse(APIModel):
    job_id: str
    created_knowledge_ids: list[str] = Field(default_factory=list)
    status: str
    message: str | None = None


class KnowledgeSummaryResponse(APIModel):
    registered_sources: int
    draft_units: int
    approved_units: int
    latest_update_at: datetime | None = None


class GraphNode(APIModel):
    id: str
    label: str
    type: str
    status: str | None = None


class GraphEdge(APIModel):
    source: str
    target: str
    type: str


class GraphResponse(APIModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
