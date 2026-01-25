import type { Insight } from "../types/insight";
import { formatConfidence } from "./shared";

export function InsightPanel({ insights }: { insights: Insight[] }) {
  return (
    <div style={styles.panel}>
      <h3 style={styles.title}>Player Insight</h3>
      {insights.map((insight, idx) => {
        const fact = insight.derivedFacts[0];
        return (
          <div key={idx} style={styles.card}>
            <div style={styles.row}><strong>Claim</strong><span>{insight.claim}</span></div>
            <div style={styles.row}><span>Value</span><span>{fact.value.toFixed(2)}</span></div>
            <div style={styles.row}><span>Baseline</span><span>{fact.baseline ?? "n/a"}</span></div>
            <div style={styles.row}><span>Δ vs baseline</span><span>{fact.baseline !== null && fact.baseline !== undefined ? (fact.value - fact.baseline).toFixed(2) : "n/a"}</span></div>
            <div style={styles.row}><span>Sample</span><span>{fact.sampleSize}</span></div>
            <div style={styles.row}><span>Confidence</span><span>{formatConfidence(insight.confidence)}</span></div>
            <div style={styles.row}><span>Explanation</span><span>{insight.explanation ?? "(LLM off / template)"}</span></div>
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  title: {
    margin: 0,
    fontSize: "16px",
    color: "#0f172a",
  },
  card: {
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    background: "#fff",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    gap: "8px",
    fontSize: "14px",
    color: "#1f2937",
  },
};
