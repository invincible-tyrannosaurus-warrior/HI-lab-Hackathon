import type { TooltipState } from "../hooks/useKnowledgeGraph";

interface NodeTooltipProps {
  tooltip: TooltipState;
}

export function NodeTooltip({ tooltip }: NodeTooltipProps) {
  if (!tooltip.visible) {
    return null;
  }

  return (
    <div
      className="node-tooltip"
      style={{
        left: tooltip.x,
        top: tooltip.y,
      }}
    >
      <strong>{tooltip.label}</strong>
      <span>{tooltip.subtitle}</span>
    </div>
  );
}
