import type React from "react";
import type { SessionAnalysis, SessionAnalysisNode } from "../types/context";

export type SessionAnalysisPanelProps = {
  analysis?: SessionAnalysis;
};

export function SessionAnalysisPanel({ analysis }: SessionAnalysisPanelProps) {
  if (!analysis) {
    return null;
  }
  const { analysis_nodes = [], entities, recently_added_node_ids = [], last_updated_at } = analysis;
  const isNew = new Set(recently_added_node_ids || []);
  const sortedNodes = [...analysis_nodes].sort((a, b) => (a.last_updated_at || "").localeCompare(b.last_updated_at || ""));

  const seriesCount = (entities?.series || []).length;
  const gamesCount = sortedNodes.reduce((acc, node) => {
    const meta = node.metadata || {};
    if (node.type === "SERIES_SAMPLE") {
      return Math.max(acc, Number(meta.sample_size) || 0);
    }
    return acc;
  }, 0);

  return (
    <section style={styles.wrapper}>
      <div style={styles.headerRow}>
        <div>
          <h3 style={styles.title}>Session Analysis</h3>
          <p style={styles.subtitle}>每次提问都在累积认知</p>
        </div>
        <div style={styles.badges}>
          <span style={styles.badge}>Series {seriesCount}</span>
          <span style={styles.badge}>Games {gamesCount}</span>
          <span style={styles.badge}>Nodes {analysis_nodes.length}</span>
        </div>
      </div>

      <div style={styles.metaRow}>
        <span>更新时间：{last_updated_at || "—"}</span>
        <span>新增节点：{recently_added_node_ids.length}</span>
      </div>

      <div style={styles.list}>
        {sortedNodes.length === 0 ? (
          <div style={styles.empty}>暂无分析节点，提问以生成。</div>
        ) : (
          sortedNodes.map((node: SessionAnalysisNode) => {
            const highlight = isNew.has(node.node_id);
            return (
              <div
                key={node.node_id}
                style={{
                  ...styles.card,
                  borderColor: highlight ? "#22c55e" : "#e5e7eb",
                  boxShadow: highlight ? "0 0 0 1px #22c55e33" : "none",
                }}
              >
                <div style={styles.cardHeader}>
                  <div style={styles.nodeType}>{node.type}</div>
                  <div style={styles.nodeSource}>{node.source}</div>
                </div>
                <div style={styles.row}>首次提问：{node.created_from_query}</div>
                <div style={styles.row}>最近更新：{node.last_updated_at}</div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    marginTop: "16px",
    padding: "16px",
    border: "1px solid #e5e7eb",
    borderRadius: "12px",
    background: "#fff",
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "8px",
  },
  title: {
    margin: 0,
    fontSize: "16px",
    color: "#0f172a",
  },
  subtitle: {
    margin: 0,
    fontSize: "13px",
    color: "#475569",
  },
  badge: {
    padding: "6px 10px",
    borderRadius: "999px",
    background: "#f0fdf4",
    color: "#16a34a",
    fontWeight: 600,
    fontSize: "13px",
    border: "1px solid #bbf7d0",
  },
  badges: {
    display: "flex",
    gap: "8px",
  },
  metaRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "12px",
    color: "#475569",
    marginBottom: "12px",
  },
  list: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
    gap: "12px",
  },
  card: {
    border: "1px solid #e5e7eb",
    borderRadius: "10px",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    background: "#fcfcfc",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "4px",
  },
  nodeType: {
    fontWeight: 700,
    color: "#0ea5e9",
    fontSize: "13px",
  },
  nodeSource: {
    fontSize: "12px",
    color: "#0f172a",
  },
  row: {
    fontSize: "12px",
    color: "#111827",
  },
  empty: {
    fontSize: "13px",
    color: "#94a3b8",
  },
};
