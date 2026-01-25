import type { AnalysisContext } from "../types/context";

export type ContextHeaderProps = {
  context: AnalysisContext;
};

export function ContextHeader({ context }: ContextHeaderProps) {
  const { player, team, match, map, timestamp, source, window } = context;
  return (
    <header style={styles.wrapper}>
      <div style={styles.row}>
        <span style={styles.label}>Player/Team</span>
        <span>{player} / {team}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Match / Map</span>
        <span>{match} / {map}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Timestamp</span>
        <span>{timestamp}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Source</span>
        <span>{source}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Window</span>
        <span>{window}</span>
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
};
