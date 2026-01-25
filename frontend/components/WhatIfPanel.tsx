import type { WhatIfOutcome, Action } from "../types/whatif";
import { formatConfidence } from "./shared";

export function WhatIfPanel({ whatIf }: { whatIf: WhatIfOutcome }) {
  return (
    <div style={styles.panel}>
      <h3 style={styles.title}>What-if Analysis</h3>
      <div style={styles.card}>
        <div style={styles.row}><strong>State</strong><span>{whatIf.state}</span></div>
        <div style={{ ...styles.row, fontWeight: 600 }}>
          <span>Action</span>
          <span>Win Prob / n</span>
        </div>
        {whatIf.actions.map((action: Action) => {
          const payload = whatIf.outcomes[action];
          const insuff = payload?.insufficient_support;
          const win = payload?.win_prob;
          const support = payload?.support ?? 0;
          return (
            <div key={action} style={styles.row}>
              <span>{action}</span>
              <span>
                {insuff || win === null ? "insufficient" : win?.toFixed(2)} (n={support})
              </span>
            </div>
          );
        })}
        <div style={styles.row}><span>Overall confidence</span><span>{formatConfidence(whatIf.confidence)}</span></div>
        <div style={styles.row}><span>Explanation</span><span>{whatIf.explanation ?? "(LLM off / template)"}</span></div>
      </div>
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
