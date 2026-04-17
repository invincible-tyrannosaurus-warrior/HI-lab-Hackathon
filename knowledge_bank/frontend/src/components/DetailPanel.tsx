import type { SelectedNode } from "../hooks/useKnowledgeGraph";
import type { KnowledgeDetailResponse, SourceResponse } from "../services/api";
import type { AdaptedGraphNode, AdaptedGraphEdge } from "../services/graphAdapter";

interface DetailPanelProps {
  selectedNode: SelectedNode | null;
  detail: KnowledgeDetailResponse | SourceResponse | null;
  loading: boolean;
  error: string | null;
  nodes: AdaptedGraphNode[];
  edges: AdaptedGraphEdge[];
  onFocusNeighbors: () => void;
  onOpenNode: (nodeId: string, nodeType: "source" | "knowledge_unit") => void;
}

function isKnowledgeDetail(
  detail: KnowledgeDetailResponse | SourceResponse | null,
): detail is KnowledgeDetailResponse {
  return Boolean(detail && "knowledge_id" in detail);
}

function isSourceDetail(detail: KnowledgeDetailResponse | SourceResponse | null): detail is SourceResponse {
  return Boolean(detail && "source_id" in detail && !("knowledge_id" in detail));
}

export function DetailPanel(props: DetailPanelProps) {
  const { selectedNode, detail, loading, error, nodes, edges, onFocusNeighbors, onOpenNode } = props;

  if (!selectedNode) {
    return (
      <aside className="detail-panel panel">
        <div className="panel-header">
          <h2>Detail Panel</h2>
          <p>Select a node from the graph or sidebar.</p>
        </div>
        <div className="empty-state">
          <strong>No node selected.</strong>
          <p>Click a knowledge unit or source file to inspect relationships, status, and provenance.</p>
        </div>
      </aside>
    );
  }

  const relatedEdges = edges.filter(
    (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id,
  );
  const relatedNodeIds = [
    ...new Set(
      relatedEdges
        .flatMap((edge) => [edge.source, edge.target])
        .filter((nodeId) => nodeId !== selectedNode.id),
    ),
  ];
  const relatedNodes = nodes.filter((node) => relatedNodeIds.includes(node.id));

  return (
    <aside className="detail-panel panel">
      <div className="panel-header">
        <h2>Detail Panel</h2>
        <p>{selectedNode.type === "knowledge_unit" ? "Knowledge unit inspection" : "Source provenance inspection"}</p>
      </div>

      <div className="detail-actions">
        <button className="ghost-button" type="button" onClick={onFocusNeighbors}>
          Focus Neighbors
        </button>
        <button
          className="ghost-button"
          type="button"
          onClick={() => {
            const nextNode = relatedNodes[0];
            if (nextNode) {
              onOpenNode(nextNode.id, nextNode.type);
            }
          }}
          disabled={!relatedNodes.length}
        >
          Open Related Nodes
        </button>
      </div>

      {loading ? (
        <div className="empty-state small">
          <strong>Loading node detail…</strong>
          <p>The right panel is fetching canonical data from the backend.</p>
        </div>
      ) : null}

      {error ? (
        <div className="empty-state small error">
          <strong>Detail fetch failed.</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {!loading && !error && isKnowledgeDetail(detail) ? (
        <div className="detail-body">
          <div className="detail-title">
            <span className={`status-badge ${detail.approval_status === "approved" ? "approved" : "draft"}`}>
              {detail.approval_status}
            </span>
            <h3>{detail.title}</h3>
            <small>{detail.knowledge_id}</small>
          </div>

          <section className="detail-section">
            <h4>Summary</h4>
            <p>{detail.summary}</p>
          </section>

          <section className="detail-section">
            <h4>Body Preview</h4>
            <p className="body-preview">{detail.body_text}</p>
          </section>

          <section className="detail-grid">
            <div><span>Module</span><strong>{detail.module_tag}</strong></div>
            <div><span>Week</span><strong>{detail.week_tag ?? "—"}</strong></div>
            <div><span>Role</span><strong>{detail.pedagogical_role}</strong></div>
            <div><span>Difficulty</span><strong>{detail.difficulty_level ?? "—"}</strong></div>
            <div><span>Version</span><strong>{detail.version_number}</strong></div>
            <div><span>Updated</span><strong>{new Date(detail.updated_at).toLocaleString()}</strong></div>
          </section>

          <section className="detail-section">
            <h4>Topic Tags</h4>
            <div className="tag-row">
              {detail.topic_tags.map((tag) => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
          </section>

          <section className="detail-section">
            <h4>Source Ref</h4>
            <div className="related-list">
              {detail.source_ref.map((sourceId) => (
                <button key={sourceId} type="button" className="linked-item" onClick={() => onOpenNode(sourceId, "source")}>
                  {sourceId}
                </button>
              ))}
            </div>
          </section>

          <section className="detail-section">
            <h4>Prerequisite Links</h4>
            <div className="related-list">
              {detail.prerequisite_links.length ? (
                detail.prerequisite_links.map((knowledgeId) => (
                  <button
                    key={knowledgeId}
                    type="button"
                    className="linked-item"
                    onClick={() => onOpenNode(knowledgeId, "knowledge_unit")}
                  >
                    {knowledgeId}
                  </button>
                ))
              ) : (
                <span className="muted">No prerequisite links stored for this unit.</span>
              )}
            </div>
          </section>
        </div>
      ) : null}

      {!loading && !error && isSourceDetail(detail) ? (
        <div className="detail-body">
          <div className="detail-title">
            <span className="status-badge source-badge">source</span>
            <h3>{detail.filename}</h3>
            <small>{detail.source_id}</small>
          </div>

          <section className="detail-grid">
            <div><span>Type</span><strong>{detail.source_type}</strong></div>
            <div><span>Uploader</span><strong>{detail.uploader}</strong></div>
            <div><span>Created</span><strong>{new Date(detail.created_at).toLocaleString()}</strong></div>
            <div><span>Module</span><strong>{detail.module_tag}</strong></div>
          </section>

          <section className="detail-section">
            <h4>Hash</h4>
            <p className="codeish">{detail.hash}</p>
          </section>

          <section className="detail-section">
            <h4>Storage Path</h4>
            <p className="codeish">{detail.storage_path}</p>
          </section>

          <section className="detail-section">
            <h4>Linked Knowledge Units</h4>
            <div className="related-list">
              {relatedNodes.length ? (
                relatedNodes
                  .filter((node) => node.type === "knowledge_unit")
                  .map((node) => (
                    <button
                      key={node.id}
                      type="button"
                      className="linked-item"
                      onClick={() => onOpenNode(node.id, "knowledge_unit")}
                    >
                      {node.label}
                    </button>
                  ))
              ) : (
                <span className="muted">No linked knowledge units in the current graph.</span>
              )}
            </div>
          </section>
        </div>
      ) : null}

      <section className="detail-section relation-section">
        <h4>Inbound / Outbound Relations</h4>
        <div className="relation-list">
          {relatedEdges.length ? (
            relatedEdges.map((edge) => {
              const isOutbound = edge.source === selectedNode.id;
              const otherId = isOutbound ? edge.target : edge.source;
              const relatedNode = nodes.find((node) => node.id === otherId);
              return (
                <button
                  key={edge.id}
                  type="button"
                  className="relation-item"
                  onClick={() => relatedNode && onOpenNode(relatedNode.id, relatedNode.type)}
                >
                  <span>{isOutbound ? "Outbound" : "Inbound"}</span>
                  <strong>{edge.type}</strong>
                  <small>{relatedNode?.label ?? otherId}</small>
                </button>
              );
            })
          ) : (
            <span className="muted">No visible relations for the selected node.</span>
          )}
        </div>
      </section>
    </aside>
  );
}
