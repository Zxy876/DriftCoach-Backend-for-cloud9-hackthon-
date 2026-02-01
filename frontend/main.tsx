import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DemoSafeFallback } from "./components/DemoSafeFallback";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary fallback={<DemoSafeFallback />}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
