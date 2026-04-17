import type { AdaptedGraphNode } from "../services/graphAdapter";

interface LeftSidebarProps {
  knowledgeNodes: AdaptedGraphNode[];
  selectedNodeId: string | null;
  sourceCount: number;
  draftCount: number;
  approvedCount: number;
  topTopics: string[];
  onSelectKnowledge: (knowledgeId: string) => void;
}

export function LeftSidebar(props: LeftSidebarProps) {
  const {
    knowledgeNodes,
    selectedNodeId,
    sourceCount,
    draftCount,
    approvedCount,
    topTopics,
    onSelectKnowledge,
  } = props;

  return (
    <aside className="left-sidebar panel">
      <div className="panel-header">
        <h2>Knowledge Units</h2>
        <p>Graph-aware operator list</p>
      </div>

      <div className="quick-stats">
        <div>
          <span>Sources</span>
          <strong>{sourceCount}</strong>
        </div>
        <div>
          <span>Draft</span>
          <strong>{draftCount}</strong>
        </div>
        <div>
          <span>Approved</span>
          <strong>{approvedCount}</strong>
        </div>
      </div>

      <div className="topic-summary">
        <span>Visible topic scope</span>
        <div className="tag-row">
          {topTopics.length ? topTopics.map((tag) => <span key={tag} className="tag">{tag}</span>) : <span className="muted">No dominant topics in current filter.</span>}
        </div>
      </div>

      <div className="knowledge-list">
        {knowledgeNodes.length ? (
          knowledgeNodes.map((node) => (
            <button
              key={node.id}
              type="button"
              className={`knowledge-list-item ${selectedNodeId === node.id ? "active" : ""}`}
              onClick={() => onSelectKnowledge(node.id)}
            >
              <div className="knowledge-list-top">
                <strong>{node.label}</strong>
                <span className={`status-badge ${node.status === "approved" ? "approved" : "draft"}`}>
                  {node.status ?? "unknown"}
                </span>
              </div>
              <div className="knowledge-meta">
                <span>{node.pedagogicalRole ?? "role?"}</span>
                <span>{node.weekTag ?? "week?"}</span>
              </div>
              <div className="tag-row compact">
                {node.topicTags.slice(0, 3).map((tag) => (
                  <span key={tag} className="tag muted-tag">
                    {tag}
                  </span>
                ))}
              </div>
            </button>
          ))
        ) : (
          <div className="empty-state small">
            <strong>No knowledge units match the current graph filters.</strong>
            <p>Try clearing the search query or widening approval and week filters.</p>
          </div>
        )}
      </div>
    </aside>
  );
}
