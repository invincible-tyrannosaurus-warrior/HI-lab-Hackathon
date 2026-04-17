import type {
  GraphApiEdge,
  GraphApiResponse,
  KnowledgeSummaryResponse,
  SourceResponse,
} from "./api";

export interface AdaptedGraphNode {
  id: string;
  label: string;
  type: "source" | "knowledge_unit";
  status: string | null;
  moduleTag: string | null;
  weekTag: string | null;
  pedagogicalRole: string | null;
  sourceType: string | null;
  topicTags: string[];
  sourceRefs: string[];
  updatedAt: string | null;
  summary: string | null;
}

export interface AdaptedGraphEdge extends GraphApiEdge {
  id: string;
}

export interface AdaptedGraph {
  nodes: AdaptedGraphNode[];
  edges: AdaptedGraphEdge[];
}

export function adaptGraphData(
  graph: GraphApiResponse,
  knowledge: KnowledgeSummaryResponse[],
  sources: SourceResponse[],
): AdaptedGraph {
  const knowledgeById = new Map(knowledge.map((item) => [item.knowledge_id, item]));
  const sourcesById = new Map(sources.map((item) => [item.source_id, item]));

  const nodes = graph.nodes.map((node) => {
    if (node.type === "knowledge_unit") {
      const detail = knowledgeById.get(node.id);
      return {
        id: node.id,
        label: node.label,
        type: "knowledge_unit" as const,
        status: detail?.approval_status ?? node.status ?? null,
        moduleTag: detail?.module_tag ?? null,
        weekTag: detail?.week_tag ?? null,
        pedagogicalRole: detail?.pedagogical_role ?? null,
        sourceType: null,
        topicTags: detail?.topic_tags ?? [],
        sourceRefs: detail?.source_ref ?? [],
        updatedAt: detail?.updated_at ?? null,
        summary: detail?.summary ?? null,
      };
    }

    const detail = sourcesById.get(node.id);
    return {
      id: node.id,
      label: node.label,
      type: "source" as const,
      status: null,
      moduleTag: detail?.module_tag ?? null,
      weekTag: detail?.week_tag ?? null,
      pedagogicalRole: null,
      sourceType: detail?.source_type ?? null,
      topicTags: [],
      sourceRefs: [],
      updatedAt: detail?.created_at ?? null,
      summary: null,
    };
  });

  const edges = graph.edges.map((edge) => ({
    ...edge,
    id: `${edge.type}:${edge.source}->${edge.target}`,
  }));

  return { nodes, edges };
}
