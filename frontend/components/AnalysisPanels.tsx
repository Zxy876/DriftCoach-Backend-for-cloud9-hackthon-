import type { Insight } from "../types/insight";
import type { ReviewAgendaItem } from "../types/review";
import type { WhatIfOutcome, Action } from "../types/whatif";

export type AnalysisPanelsProps = {
  insights: Insight[];
  review: ReviewAgendaItem[];
  whatIf: WhatIfOutcome;
};

export function AnalysisPanels({ insights, review, whatIf }: AnalysisPanelsProps) {
  return (
    <section style={styles.wrapper}>
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

      <div style={styles.panel}>
        <h3 style={styles.title}>Post-match Review</h3>
        {review.map((item, idx) => {
          const fact = item.evidence[0];
          return (
            <div key={idx} style={styles.card}>
              <div style={styles.row}><strong>Agenda</strong><span>{item.topic}</span></div>
              <div style={styles.row}><span>Why</span><span>{fact.factType}</span></div>
              <div style={styles.row}><span>Evidence</span><span>{fact.value.toFixed(2)} (baseline {fact.baseline ?? "n/a"}, n={fact.sampleSize})</span></div>
              <div style={styles.row}><span>States</span><span>{item.statesInvolved.join(", ")}</span></div>
              <div style={styles.row}><span>Confidence</span><span>{formatConfidence(item.confidence)}</span></div>
              <div style={styles.row}><span>Explanation</span><span>{item.explanation ?? "(LLM off / template)"}</span></div>
            </div>
          );
        })}
      </div>

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
                  {insuff || win === null ? "insufficient" : win?.toFixed(2)}
                  {" "}(n={support})
                </span>
              </div>
            );
          })}
          <div style={styles.row}><span>Overall confidence</span><span>{formatConfidence(whatIf.confidence)}</span></div>
          <div style={styles.row}><span>Explanation</span><span>{whatIf.explanation ?? "(LLM off / template)"}</span></div>
        </div>
      </div>
    </section>
  );
}

function formatConfidence(conf: number): string {
  const clamped = Math.max(0, Math.min(conf, 1));
  if (clamped >= 0.75) return `${clamped.toFixed(2)} (strong)`;
  if (clamped >= 0.5) return `${clamped.toFixed(2)} (moderate)`;
  return `${clamped.toFixed(2)} (weak)`;
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "16px",
    marginTop: "16px",
  },
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
