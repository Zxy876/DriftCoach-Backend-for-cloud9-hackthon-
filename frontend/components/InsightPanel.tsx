import type { Insight } from "../types/insight";
import { formatConfidence } from "./shared";

function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div style={styles.empty}>
      <div style={{ fontWeight: 600 }}>{title}</div>
      {description ? <div style={{ color: "#475569", fontSize: "13px" }}>{description}</div> : null}
    </div>
  );
}

export function InsightPanel({ insights }: { insights: Insight[] | undefined }) {
  const safeInsights = insights || [];

  if (!safeInsights.length) {
    return <EmptyState title="尚未生成分析" description="请输入自然语言问题以触发分析挖掘" />;
  }

  return (
    <div style={styles.panel}>
      <h3 style={styles.title}>Player Insight</h3>
      {safeInsights.map((insight, idx) => {
        const fact = insight.derivedFacts && insight.derivedFacts.length > 0 ? insight.derivedFacts[0] : undefined;
        return (
          <div key={idx} style={styles.card}>
            <div style={styles.row}><strong>Claim</strong><span>{insight.claim}</span></div>
            <div style={styles.row}><span>Value</span><span>{fact?.value !== undefined ? Number(fact.value).toFixed(2) : "n/a"}</span></div>
            <div style={styles.row}><span>Baseline</span><span>{fact?.baseline ?? "n/a"}</span></div>
            <div style={styles.row}><span>Δ vs baseline</span><span>{fact && fact.baseline !== null && fact.baseline !== undefined && fact.value !== undefined ? (Number(fact.value) - Number(fact.baseline)).toFixed(2) : "n/a"}</span></div>
            <div style={styles.row}><span>Sample</span><span>{fact?.sampleSize ?? "n/a"}</span></div>
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
  empty: {
    border: "1px dashed #e5e7eb",
    borderRadius: "8px",
    padding: "12px",
    background: "#f8fafc",
  },
};
