import type { AnalysisContext } from "../types/context";

export type ContextHeaderProps = {
  context?: AnalysisContext | null;
};

export function ContextHeader({ context }: ContextHeaderProps) {
  if (!context) {
    return (
      <header style={styles.wrapper}>
        <div style={styles.placeholder}>Context unavailable</div>
      </header>
    );
  }

  const safeContext = context ?? {};
  const player = safeContext.player ?? null;
  const team = safeContext.team ?? null;
  const match = safeContext.match ?? null;
  const map = safeContext.map ?? null;
  const timestamp = safeContext.timestamp ?? null;
  const source = safeContext.source ?? "unknown";
  const window = safeContext.window ?? null;

  const dataSource = String(source).startsWith("grid")
    ? (source === "grid-fallback" ? "GRID API · Limited Sample" : "GRID API")
    : "Mock Demo";
  return (
    <header style={styles.wrapper}>
      <div style={styles.row}>
        <span style={styles.label}>Player/Team</span>
        <span>{player ?? "-"} / {team ?? "-"}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Match / Map</span>
        <span>{match ?? "-"} / {map ?? "-"}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Timestamp</span>
        <span>{timestamp ?? "-"}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Source</span>
        <span>{dataSource}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Window</span>
        <span>{window ?? "-"}</span>
      </div>
    </header>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "8px 16px",
    padding: "16px",
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    background: "#f8fafc",
    fontSize: "14px",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    gap: "8px",
  },
  label: {
    color: "#475569",
    fontWeight: 600,
  },
  placeholder: {
    color: "#94a3b8",
    fontStyle: "italic",
  },
};
