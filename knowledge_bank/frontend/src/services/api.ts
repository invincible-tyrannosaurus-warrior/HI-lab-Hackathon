export type ApprovalStatus = "draft" | "approved";

export interface GraphApiNode {
  id: string;
  label: string;
  type: "source" | "knowledge_unit";
  status?: ApprovalStatus | null;
}

export interface GraphApiEdge {
  source: string;
  target: string;
  type: "derived_from" | "prerequisite" | string;
}

export interface GraphApiResponse {
  nodes: GraphApiNode[];
  edges: GraphApiEdge[];
}

export interface KnowledgeSummaryResponse {
  knowledge_id: string;
  title: string;
  summary: string;
  module_tag: string;
  week_tag: string | null;
  topic_tags: string[];
  pedagogical_role: string;
  approval_status: ApprovalStatus;
  source_ref: string[];
  version_number: number;
  updated_at: string;
}

export interface KnowledgeDetailResponse extends KnowledgeSummaryResponse {
  body_text: string;
  difficulty_level: string | null;
  source_type: string;
  prerequisite_links: string[];
  learning_outcome_links: string[];
  created_at: string;
}

export interface SourceResponse {
  source_id: string;
  filename: string;
  source_type: string;
  module_tag: string;
  week_tag: string | null;
  uploader: string;
  hash: string;
  storage_path: string;
  created_at: string;
}

export interface KnowledgeSummaryCounts {
  registered_sources: number;
  draft_units: number;
  approved_units: number;
  latest_update_at: string | null;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

function buildUrl(path: string, params?: Record<string, string | undefined | null>): string {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (!value) {
        continue;
      }
      url.searchParams.set(key, value);
    }
  }
  return API_BASE ? url.toString() : `${url.pathname}${url.search}`;
}

async function apiGet<T>(path: string, params?: Record<string, string | undefined | null>): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`GET ${path} failed: ${response.status} ${detail}`);
  }

  return (await response.json()) as T;
}

export function fetchGraph(): Promise<GraphApiResponse> {
  return apiGet<GraphApiResponse>("/knowledge/graph");
}

export function fetchSummary(): Promise<KnowledgeSummaryCounts> {
  return apiGet<KnowledgeSummaryCounts>("/knowledge/summary");
}

export function fetchKnowledgeSearch(
  params?: Record<string, string | undefined | null>,
): Promise<KnowledgeSummaryResponse[]> {
  return apiGet<KnowledgeSummaryResponse[]>("/knowledge/search", params);
}

export function fetchKnowledgeDetail(knowledgeId: string): Promise<KnowledgeDetailResponse> {
  return apiGet<KnowledgeDetailResponse>(`/knowledge/${knowledgeId}`);
}

export function fetchSources(
  params?: Record<string, string | undefined | null>,
): Promise<SourceResponse[]> {
  return apiGet<SourceResponse[]>("/sources", params);
}

export function fetchSourceDetail(sourceId: string): Promise<SourceResponse> {
  return apiGet<SourceResponse>(`/sources/${sourceId}`);
}
