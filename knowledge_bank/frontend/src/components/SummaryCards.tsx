import type { KnowledgeSummaryCounts } from "../services/api";

interface SummaryCardsProps {
  summary: KnowledgeSummaryCounts | null;
  visibleKnowledgeCount: number;
  visibleSourceCount: number;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Unavailable";
  }
  return new Date(value).toLocaleString();
}

export function SummaryCards(props: SummaryCardsProps) {
  const { summary, visibleKnowledgeCount, visibleSourceCount } = props;

  return (
    <div className="summary-grid">
      <article className="summary-card">
        <span>Total Sources</span>
        <strong>{summary?.registered_sources ?? "—"}</strong>
        <small>{visibleSourceCount} visible in current graph</small>
      </article>
      <article className="summary-card">
        <span>Draft Units</span>
        <strong>{summary?.draft_units ?? "—"}</strong>
        <small>Pending approval</small>
      </article>
      <article className="summary-card">
        <span>Approved Units</span>
        <strong>{summary?.approved_units ?? "—"}</strong>
        <small>{visibleKnowledgeCount} visible after filters</small>
      </article>
      <article className="summary-card">
        <span>Latest Update</span>
        <strong className="summary-date">{formatTimestamp(summary?.latest_update_at ?? null)}</strong>
        <small>Bundle contract freshness</small>
      </article>
    </div>
  );
}
