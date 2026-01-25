import { ContextHeader } from "./components/ContextHeader";
import { InsightPanel } from "./components/InsightPanel";
import { ReviewPanel } from "./components/ReviewPanel";
import { WhatIfPanel } from "./components/WhatIfPanel";
import type { DemoPayload } from "./types/context";
import { renderInsight, renderReview, renderWhatIf, type RenderMode } from "./llm/render";

// Using require to avoid JSON module config requirements
// In bundler environments, you can switch to import demo from "./mocks/demo.json";
const demo: DemoPayload = require("./mocks/demo.json");

export function App() {
  const renderMode: RenderMode = "template"; // could be toggled via UI
  const enriched = {
    ...demo,
    insights: demo.insights.map((i) => ({ ...i, explanation: renderInsight(i, { mode: renderMode }) })),
    review: demo.review.map((r) => ({ ...r, explanation: renderReview(r, { mode: renderMode }) })),
    whatIf: { ...demo.whatIf, explanation: renderWhatIf(demo.whatIf, { mode: renderMode }) },
  } satisfies DemoPayload;

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>DriftCoach Frontend Demo</h2>
      <p style={styles.subtitle}>Demo flow (frozen order): 1) Player Insight → 2) Post-match Review → 3) What-if Analysis</p>
      <ContextHeader context={enriched.context} />
      <div style={styles.panels}>
        <InsightPanel insights={enriched.insights} />
        <ReviewPanel review={enriched.review} />
        <WhatIfPanel whatIf={enriched.whatIf} />
      </div>
      <section style={styles.assumptions}>
        <strong>Assumptions & Limits（frozen, always visible）</strong>
        <ul style={{ margin: 0, paddingLeft: "20px" }}>
          <li>Based on similar historical states</li>
          <li>Signal strength: weak / moderate / strong</li>
          <li>This is not a recommendation</li>
        </ul>
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    fontFamily: "Inter, -apple-system, system-ui, sans-serif",
    padding: "24px",
    background: "#f5f7fb",
    color: "#0f172a",
  },
  heading: {
    marginTop: 0,
    marginBottom: "12px",
  },
  subtitle: {
    marginTop: 0,
    marginBottom: "12px",
    color: "#475569",
    fontSize: "14px",
  },
  panels: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "16px",
    marginTop: "16px",
  },
  assumptions: {
    marginTop: "24px",
    border: "1px dashed #cbd5e1",
    borderRadius: "8px",
    padding: "12px",
    background: "#fff",
    fontSize: "14px",
  },
};
