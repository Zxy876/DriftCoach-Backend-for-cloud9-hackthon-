import type { ReviewAgendaItem } from "../types/review";
import { formatConfidence } from "./shared";

function EmptyState() {
  return (
    <div style={styles.empty}>暂无复盘议程</div>
  );
}

export function ReviewPanel({ review }: { review?: ReviewAgendaItem[] | null }) {
  const items = Array.isArray(review) ? review : [];

  if (!items.length) {
    return (
      <div style={styles.panel}>
        <h3 style={styles.title}>Post-match Review</h3>
        <EmptyState />
      </div>
    );
  }
  return (
    <div style={styles.panel}>
      <h3 style={styles.title}>Post-match Review</h3>
      {items.map((item, idx) => {
        const evidence = Array.isArray(item.evidence) ? item.evidence : [];
        const fact = evidence[0];
        const value = typeof fact?.value === "number" ? fact.value.toFixed(2) : "n/a";
        const baseline = fact?.baseline ?? "n/a";
        const sample = fact?.sampleSize ?? "n/a";
        const states = Array.isArray(item.statesInvolved) ? item.statesInvolved.join(", ") : "n/a";
        return (
          <div key={idx} style={styles.card}>
            <div style={styles.row}><strong>Agenda</strong><span>{item.topic}</span></div>
            <div style={styles.row}><span>Why</span><span>{fact?.factType || "n/a"}</span></div>
            <div style={styles.row}><span>Evidence</span><span>{value} (baseline {baseline}, n={sample})</span></div>
            <div style={styles.row}><span>States</span><span>{states}</span></div>
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
  empty: {
    border: "1px dashed #e5e7eb",
    borderRadius: "8px",
    padding: "12px",
    background: "#f8fafc",
    color: "#475569",
    fontSize: "13px",
  },
};
