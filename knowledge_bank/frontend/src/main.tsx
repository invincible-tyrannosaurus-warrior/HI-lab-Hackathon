import React from "react";
import ReactDOM from "react-dom/client";

import { KnowledgeBankPage } from "./pages/KnowledgeBankPage";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <KnowledgeBankPage />
  </React.StrictMode>,
);
