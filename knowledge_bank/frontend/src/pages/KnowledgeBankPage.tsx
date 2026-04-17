import { useEffect } from "react";

import { DetailPanel } from "../components/DetailPanel";
import { GraphToolbar } from "../components/GraphToolbar";
import { KnowledgeGraph } from "../components/KnowledgeGraph";
import { LeftSidebar } from "../components/LeftSidebar";
import { SummaryCards } from "../components/SummaryCards";
import { useKnowledgeGraph } from "../hooks/useKnowledgeGraph";

function filterSummary(filters: {
  moduleTag: string;
  approvalStatus: string;
  pedagogicalRole: string;
  weekTag: string;
  sourceType: string;
}): string {
  const active = Object.entries(filters)
    .filter(([, value]) => value !== "all")
    .map(([key, value]) => `${key}=${value}`);
  return active.length ? active.join(", ") : "none";
}

export function KnowledgeBankPage() {
  const graphState = useKnowledgeGraph();
  const {
    visibleNodes,
    visibleEdges,
    visibleKnowledgeNodes,
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
  } = graphState;

  useEffect(() => {
    if (!selectedNode && visibleKnowledgeNodes.length) {
      selectNode({ id: visibleKnowledgeNodes[0].id, type: "knowledge_unit" });
    }
  }, [selectedNode, selectNode, visibleKnowledgeNodes]);

  const visibleSources = visibleNodes.filter((node) => node.type === "source");
  const visibleDraftCount = visibleKnowledgeNodes.filter((node) => node.status === "draft").length;
  const visibleApprovedCount = visibleKnowledgeNodes.filter((node) => node.status === "approved").length;

  return (
    <main className="knowledge-shell">
      <GraphToolbar
        modules={availableModules}
        weeks={availableWeeks}
        roles={availableRoles}
        sourceTypes={availableSourceTypes}
        filters={filters}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onFiltersChange={setFilters}
        onRefresh={() => void refreshGraph()}
        onFitGraph={fitGraph}
        onSearchSubmit={focusFirstSearchMatch}
      />

      <SummaryCards
        summary={summary}
        visibleKnowledgeCount={visibleKnowledgeNodes.length}
        visibleSourceCount={visibleSources.length}
      />

      <section className="layout-grid">
        <LeftSidebar
          knowledgeNodes={visibleKnowledgeNodes}
          selectedNodeId={selectedNode?.id ?? null}
          sourceCount={visibleSources.length}
          draftCount={visibleDraftCount}
          approvedCount={visibleApprovedCount}
          topTopics={topTopics}
          onSelectKnowledge={(knowledgeId) => selectNode({ id: knowledgeId, type: "knowledge_unit" })}
        />

        <section className="graph-column">
          {loading ? (
            <div className="panel large-panel">
              <div className="empty-state">
                <strong>Loading knowledge graph…</strong>
                <p>Pulling `/knowledge/graph`, `/knowledge/search`, `/sources`, and `/knowledge/summary`.</p>
              </div>
            </div>
          ) : error ? (
            <div className="panel large-panel">
              <div className="empty-state error">
                <strong>Graph load failed.</strong>
                <p>{error}</p>
              </div>
            </div>
          ) : (
            <KnowledgeGraph
              nodes={visibleNodes}
              edges={visibleEdges}
              selectedNodeId={selectedNode?.id ?? null}
              searchQuery={searchQuery}
              fitGraphNonce={fitGraphNonce}
              focusNonce={focusNonce}
              onSelectNode={(nodeId, nodeType) => selectNode({ id: nodeId, type: nodeType })}
            />
          )}
        </section>

        <DetailPanel
          selectedNode={selectedNode}
          detail={selectedDetail}
          loading={detailLoading}
          error={detailError}
          nodes={visibleNodes}
          edges={visibleEdges}
          onFocusNeighbors={focusNeighbors}
          onOpenNode={(nodeId, nodeType) => selectNode({ id: nodeId, type: nodeType })}
        />
      </section>

      <footer className="status-footer">
        <span>
          <strong>{visibleNodes.length}</strong> nodes
        </span>
        <span>
          <strong>{visibleEdges.length}</strong> edges
        </span>
        <span>
          selected: <strong>{selectedNode ? 1 : 0}</strong>
        </span>
        <span>
          filters: <strong>{filterSummary(filters)}</strong>
        </span>
        <span className={`connectivity ${connectivity}`}>
          backend: <strong>{connectivity}</strong>
        </span>
      </footer>
    </main>
  );
}
