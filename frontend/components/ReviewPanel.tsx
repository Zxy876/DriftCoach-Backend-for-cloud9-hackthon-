import type { ReviewAgendaItem } from "../types/review";
import { formatConfidence } from "./shared";

export function ReviewPanel({ review }: { review: ReviewAgendaItem[] }) {
  return (
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
