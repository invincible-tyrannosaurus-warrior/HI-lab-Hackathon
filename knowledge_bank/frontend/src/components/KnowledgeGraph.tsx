import { useEffect, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import type { Core } from "cytoscape";

import type { TooltipState } from "../hooks/useKnowledgeGraph";
import type { AdaptedGraphEdge, AdaptedGraphNode } from "../services/graphAdapter";
import { NodeTooltip } from "./NodeTooltip";

interface KnowledgeGraphProps {
  nodes: AdaptedGraphNode[];
  edges: AdaptedGraphEdge[];
  selectedNodeId: string | null;
  searchQuery: string;
  fitGraphNonce: number;
  focusNonce: number;
  onSelectNode: (nodeId: string, nodeType: "source" | "knowledge_unit") => void;
}

function buildElements(
  nodes: AdaptedGraphNode[],
  edges: AdaptedGraphEdge[],
  selectedNodeId: string | null,
  searchQuery: string,
) {
  const normalizedSearch = searchQuery.trim().toLowerCase();
  const neighborIds = new Set<string>();
  const incidentEdgeIds = new Set<string>();

  if (selectedNodeId) {
    for (const edge of edges) {
      if (edge.source === selectedNodeId || edge.target === selectedNodeId) {
        neighborIds.add(edge.source);
        neighborIds.add(edge.target);
        incidentEdgeIds.add(edge.id);
      }
    }
  }

  const nodeElements = nodes.map((node) => {
    const classes: string[] = [node.type];
    if (node.type === "knowledge_unit") {
      classes.push(node.status === "approved" ? "approved" : "draft");
    }
    if (selectedNodeId === node.id) {
      classes.push("selected");
    } else if (selectedNodeId) {
      if (neighborIds.has(node.id)) {
        classes.push("neighbor");
      } else {
        classes.push("faded");
      }
    }
    if (
      normalizedSearch &&
      [node.label, node.id, node.topicTags.join(" ")].join(" ").toLowerCase().includes(normalizedSearch)
    ) {
      classes.push("search-hit");
    }

    return {
      data: {
        id: node.id,
        label: node.label,
        nodeType: node.type,
        status: node.status ?? "",
        subtitle: node.type === "source" ? node.sourceType ?? "source" : node.pedagogicalRole ?? "knowledge unit",
      },
      classes: classes.join(" "),
    };
  });

  const edgeElements = edges.map((edge) => {
    const classes = [edge.type];
    if (selectedNodeId) {
      classes.push(incidentEdgeIds.has(edge.id) ? "connected" : "faded");
    }
    return {
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        edgeType: edge.type,
      },
      classes: classes.join(" "),
    };
  });

  return [...nodeElements, ...edgeElements];
}

const stylesheet = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "font-size": 11,
      color: "#e4eef8",
      "text-wrap": "wrap",
      "text-max-width": 120,
      "text-valign": "center",
      "text-halign": "center",
      width: 54,
      height: 54,
      "background-color": "#63748a",
      "border-color": "#8ea2b8",
      "border-width": 1.5,
      "overlay-opacity": 0,
      "transition-property": "background-color, border-color, opacity",
      "transition-duration": "120ms",
    },
  },
  {
    selector: "node.knowledge_unit",
    style: {
      shape: "ellipse",
      width: 68,
      height: 68,
    },
  },
  {
    selector: "node.source",
    style: {
      shape: "round-rectangle",
      width: 84,
      height: 44,
      "background-color": "#2d3745",
      "border-color": "#6b7d93",
    },
  },
  {
    selector: "node.approved",
    style: {
      "background-color": "#1b6b53",
      "border-color": "#68d2a7",
    },
  },
  {
    selector: "node.draft",
    style: {
      "background-color": "#235385",
      "border-color": "#78b5ff",
    },
  },
  {
    selector: "node.selected",
    style: {
      "border-width": 3,
      "border-color": "#f3f7fc",
      "shadow-color": "#95d9ff",
      "shadow-blur": 18,
      "shadow-opacity": 0.55,
      "z-index": 10,
    },
  },
  {
    selector: "node.neighbor",
    style: {
      "shadow-color": "#7d95ad",
      "shadow-blur": 10,
      "shadow-opacity": 0.35,
    },
  },
  {
    selector: "node.search-hit",
    style: {
      "border-color": "#ffe08a",
      "border-width": 3,
    },
  },
  {
    selector: "node.faded",
    style: {
      opacity: 0.23,
    },
  },
  {
    selector: "edge",
    style: {
      width: 2,
      "line-color": "#5d7088",
      "target-arrow-color": "#5d7088",
      "curve-style": "bezier",
      opacity: 0.82,
    },
  },
  {
    selector: "edge.derived_from",
    style: {
      "line-color": "#5ca6db",
      "target-arrow-color": "#5ca6db",
      "target-arrow-shape": "triangle",
    },
  },
  {
    selector: "edge.prerequisite",
    style: {
      "line-color": "#8e76d6",
      "target-arrow-color": "#8e76d6",
      "target-arrow-shape": "triangle",
      "line-style": "dashed",
    },
  },
  {
    selector: "edge.connected",
    style: {
      width: 3,
      opacity: 1,
    },
  },
  {
    selector: "edge.faded",
    style: {
      opacity: 0.18,
    },
  },
];

export function KnowledgeGraph(props: KnowledgeGraphProps) {
  const { nodes, edges, selectedNodeId, searchQuery, fitGraphNonce, focusNonce, onSelectNode } = props;
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    label: "",
    subtitle: "",
  });
  const cyRef = useRef<Core | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const elements = buildElements(nodes, edges, selectedNodeId, searchQuery);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }

    const handleTap = (event: any) => {
      const node = event.target;
      onSelectNode(node.id(), node.data("nodeType"));
    };

    const handleHover = (event: any) => {
      const bounds = containerRef.current?.getBoundingClientRect();
      const rendered = event.renderedPosition;
      setTooltip({
        visible: true,
        x: (bounds?.left ?? 0) + rendered.x + 18,
        y: (bounds?.top ?? 0) + rendered.y + 18,
        label: event.target.data("label"),
        subtitle: event.target.data("subtitle"),
      });
    };

    const handleHoverOut = () => {
      setTooltip((current) => ({ ...current, visible: false }));
    };

    cy.on("tap", "node", handleTap);
    cy.on("mouseover", "node", handleHover);
    cy.on("mouseout", "node", handleHoverOut);

    return () => {
      cy.off("tap", "node", handleTap);
      cy.off("mouseover", "node", handleHover);
      cy.off("mouseout", "node", handleHoverOut);
    };
  }, [onSelectNode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    cy.layout({ name: "cose", animate: false, fit: true, padding: 32 }).run();
  }, [nodes.length, edges.length]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !selectedNodeId) {
      return;
    }
    const selected = cy.getElementById(selectedNodeId);
    if (!selected.nonempty()) {
      return;
    }
    cy.animate({
      fit: {
        eles: selected.closedNeighborhood(),
        padding: 92,
      },
      duration: 280,
    });
  }, [selectedNodeId, focusNonce]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    cy.animate({
      fit: {
        eles: cy.elements(),
        padding: 56,
      },
      duration: 220,
    });
  }, [fitGraphNonce]);

  return (
    <div className="graph-panel panel" ref={containerRef}>
      <div className="panel-header graph-panel-header">
        <div>
          <h2>Graph Canvas</h2>
          <p>Source-to-knowledge and prerequisite relationships</p>
        </div>
        <div className="legend">
          <span><i className="dot approved" /> Approved</span>
          <span><i className="dot draft" /> Draft</span>
          <span><i className="dot source" /> Source</span>
        </div>
      </div>

      <div className="graph-surface">
        {nodes.length ? (
          <CytoscapeComponent
            elements={elements}
            style={{ width: "100%", height: "100%" }}
            stylesheet={stylesheet}
            cy={(cy: Core) => {
              cyRef.current = cy;
            }}
            minZoom={0.35}
            maxZoom={2.2}
            wheelSensitivity={0.24}
          />
        ) : (
          <div className="empty-state">
            <strong>No nodes are visible.</strong>
            <p>Relax the current filters or refresh the Knowledge Bank graph.</p>
          </div>
        )}
      </div>

      <NodeTooltip tooltip={tooltip} />
    </div>
  );
}
