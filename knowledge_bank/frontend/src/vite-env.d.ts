/// <reference types="vite/client" />

declare module "react-cytoscapejs" {
  import type { ComponentType, CSSProperties } from "react";
  import type { Core } from "cytoscape";

  interface CytoscapeComponentProps {
    elements: unknown;
    stylesheet?: unknown;
    style?: CSSProperties;
    layout?: unknown;
    minZoom?: number;
    maxZoom?: number;
    wheelSensitivity?: number;
    cy?: (cy: Core) => void;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
