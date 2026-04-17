import { useDeferredValue, useEffect, useState } from "react";

import {
  fetchGraph,
  fetchKnowledgeDetail,
  fetchKnowledgeSearch,
  fetchSourceDetail,
  fetchSources,
  fetchSummary,
  type KnowledgeDetailResponse,
  type KnowledgeSummaryCounts,
  type KnowledgeSummaryResponse,
  type SourceResponse,
} from "../services/api";
import { adaptGraphData, type AdaptedGraph, type AdaptedGraphNode } from "../services/graphAdapter";

export interface GraphFilters {
  moduleTag: string;
  approvalStatus: string;
  pedagogicalRole: string;
  weekTag: string;
  sourceType: string;
}

export interface SelectedNode {
  id: string;
  type: "source" | "knowledge_unit";
}

export interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  label: string;
  subtitle: string;
}

export function useKnowledgeGraph() {
  const [graph, setGraph] = useState<AdaptedGraph>({ nodes: [], edges: [] });
  const [knowledge, setKnowledge] = useState<KnowledgeSummaryResponse[]>([]);
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [summary, setSummary] = useState<KnowledgeSummaryCounts | null>(null);
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<KnowledgeDetailResponse | SourceResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectivity, setConnectivity] = useState<"loading" | "online" | "offline">("loading");
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [filters, setFilters] = useState<GraphFilters>({
    moduleTag: "all",
    approvalStatus: "all",
    pedagogicalRole: "all",
    weekTag: "all",
    sourceType: "all",
  });
  const [fitGraphNonce, setFitGraphNonce] = useState(0);
  const [focusNonce, setFocusNonce] = useState(0);

  async function refreshGraph(): Promise<void> {
    setLoading(true);
    setError(null);
    setConnectivity("loading");
    try {
      const [graphResponse, summaryResponse, knowledgeResponse, sourceResponse] = await Promise.all([
        fetchGraph(),
        fetchSummary(),
        fetchKnowledgeSearch(),
        fetchSources(),
      ]);
      setGraph(adaptGraphData(graphResponse, knowledgeResponse, sourceResponse));
      setKnowledge(knowledgeResponse);
      setSources(sourceResponse);
      setSummary(summaryResponse);
      setConnectivity("online");
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Failed to load Knowledge Bank graph.");
      setConnectivity("offline");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshGraph();
  }, []);

  useEffect(() => {
    if (!selectedNode) {
      setSelectedDetail(null);
      setDetailError(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);

    const request =
      selectedNode.type === "knowledge_unit"
        ? fetchKnowledgeDetail(selectedNode.id)
        : fetchSourceDetail(selectedNode.id);

    request
      .then((response) => {
        if (!cancelled) {
          setSelectedDetail(response);
        }
      })
      .catch((detailFetchError) => {
        if (!cancelled) {
          setSelectedDetail(null);
          setDetailError(
            detailFetchError instanceof Error
              ? detailFetchError.message
              : "Failed to load selected node detail.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDetailLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedNode]);

  const availableModules = [
    ...new Set(graph.nodes.map((node) => node.moduleTag).filter((value): value is string => Boolean(value))),
  ].sort();
  const availableWeeks = [
    ...new Set(graph.nodes.map((node) => node.weekTag).filter((value): value is string => Boolean(value))),
  ].sort();
  const availableRoles = [
    ...new Set(
      graph.nodes
        .map((node) => node.pedagogicalRole)
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort();
  const availableSourceTypes = [
    ...new Set(
      graph.nodes.map((node) => node.sourceType).filter((value): value is string => Boolean(value)),
    ),
  ].sort();

  const normalizedSearch = deferredSearchQuery.trim().toLowerCase();

  function matchesSearch(node: AdaptedGraphNode): boolean {
    if (!normalizedSearch) {
      return true;
    }

    const searchFields = [
      node.label,
      node.id,
      node.summary ?? "",
      node.topicTags.join(" "),
      node.sourceType ?? "",
    ]
      .join(" ")
      .toLowerCase();
    return searchFields.includes(normalizedSearch);
  }

  function matchesFilters(node: AdaptedGraphNode): boolean {
    if (filters.moduleTag !== "all" && node.moduleTag !== filters.moduleTag) {
      return false;
    }
    if (filters.weekTag !== "all" && node.weekTag !== filters.weekTag) {
      return false;
    }
    if (node.type === "knowledge_unit") {
      if (filters.approvalStatus !== "all" && node.status !== filters.approvalStatus) {
        return false;
      }
      if (filters.pedagogicalRole !== "all" && node.pedagogicalRole !== filters.pedagogicalRole) {
        return false;
      }
    }
    if (node.type === "source") {
      if (filters.sourceType !== "all" && node.sourceType !== filters.sourceType) {
        return false;
      }
    }
    return true;
  }

  const visibleKnowledgeNodes = graph.nodes.filter(
    (node) => node.type === "knowledge_unit" && matchesFilters(node) && matchesSearch(node),
  );
  const visibleKnowledgeIds = new Set(visibleKnowledgeNodes.map((node) => node.id));

  const visibleSourceIds = new Set<string>();
  for (const edge of graph.edges) {
    if (edge.type === "derived_from" && visibleKnowledgeIds.has(edge.target)) {
      visibleSourceIds.add(edge.source);
    }
  }

  const visibleNodes = graph.nodes.filter((node) => {
    if (!matchesFilters(node)) {
      return false;
    }
    if (node.type === "knowledge_unit") {
      return visibleKnowledgeIds.has(node.id);
    }
    if (node.type === "source") {
      if (normalizedSearch && !matchesSearch(node) && !visibleSourceIds.has(node.id)) {
        return false;
      }
      return visibleSourceIds.has(node.id) || matchesSearch(node);
    }
    return true;
  });

  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = graph.edges.filter(
    (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target),
  );

  const topicSummary = visibleKnowledgeNodes
    .flatMap((node) => node.topicTags)
    .reduce<Record<string, number>>((accumulator, tag) => {
      accumulator[tag] = (accumulator[tag] ?? 0) + 1;
      return accumulator;
    }, {});
  const topTopics = Object.entries(topicSummary)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 5)
    .map(([tag]) => tag);

  const selectedNodeStillVisible = selectedNode ? visibleNodeIds.has(selectedNode.id) : false;
  useEffect(() => {
    if (selectedNode && !selectedNodeStillVisible) {
      setSelectedNode(null);
      setSelectedDetail(null);
    }
  }, [selectedNode, selectedNodeStillVisible]);

  function selectNode(node: SelectedNode | null): void {
    setSelectedNode(node);
    setFocusNonce((value) => value + 1);
  }

  function focusNeighbors(): void {
    if (!selectedNode) {
      return;
    }
    setFocusNonce((value) => value + 1);
  }

  function fitGraph(): void {
    setFitGraphNonce((value) => value + 1);
  }

  function focusFirstSearchMatch(): void {
    const knowledgeNode = visibleKnowledgeNodes[0];
    if (knowledgeNode) {
      selectNode({ id: knowledgeNode.id, type: "knowledge_unit" });
      return;
    }
    const sourceNode = visibleNodes.find((node) => node.type === "source");
    if (sourceNode) {
      selectNode({ id: sourceNode.id, type: "source" });
    }
  }

  return {
    graph,
    visibleNodes,
    visibleEdges,
    visibleKnowledgeNodes,
    knowledge,
    sources,
    summary,
    loading,
    error,
    connectivity,
    selectedNode,
    selectedDetail,
    detailLoading,
    detailError,
    searchQuery,
    setSearchQuery,
    filters,
    setFilters,
    availableModules,
    availableWeeks,
    availableRoles,
    availableSourceTypes,
    topTopics,
    refreshGraph,
    selectNode,
    focusNeighbors,
    fitGraph,
    focusFirstSearchMatch,
    fitGraphNonce,
    focusNonce,
  };
}
