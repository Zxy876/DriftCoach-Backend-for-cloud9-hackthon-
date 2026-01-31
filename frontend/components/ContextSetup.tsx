import { useState } from "react";

interface Props {
  defaultPlayerId?: string;
  defaultSeriesId?: string;
  loading?: boolean;
  contextLoaded?: boolean;
  onLoad: (playerId: string | undefined, seriesId: string) => Promise<void> | void;
}

export function ContextSetup({ defaultPlayerId = "", defaultSeriesId = "", loading, contextLoaded, onLoad }: Props) {
  const [playerId, setPlayerId] = useState(defaultPlayerId);
  const [seriesId, setSeriesId] = useState(defaultSeriesId);
  const [showAdvanced, setShowAdvanced] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!seriesId.trim()) return;
    const playerArg = playerId.trim() || undefined;
    await onLoad(playerArg, seriesId.trim());
  }

  return (
    <section style={styles.container}>
      <div style={styles.headerRow}>
        <h3 style={styles.heading}>Context Setup</h3>
        {contextLoaded ? <span style={styles.badgeReady}>READY</span> : <span style={styles.badgeIdle}>Not loaded</span>}
      </div>
      <form onSubmit={handleSubmit} style={styles.form}>
        <label style={styles.label}>
          GRID_SERIES_ID
          <input
            value={seriesId}
            onChange={(e) => setSeriesId(e.target.value)}
            placeholder="e.g., 2819676"
            style={styles.input}
            disabled={loading}
          />
        </label>
        <div style={styles.advancedBox}>
          <button type="button" style={styles.toggle} onClick={() => setShowAdvanced((v) => !v)} disabled={loading}>
            {showAdvanced ? "Hide Advanced" : "Show Advanced"}
          </button>
          {showAdvanced ? (
            <label style={{ ...styles.label, marginTop: "8px" }}>
              GRID_PLAYER_ID（可选，仅 Debug/Advanced）
              <input
                value={playerId}
                onChange={(e) => setPlayerId(e.target.value)}
                placeholder="e.g., 91"
                style={styles.input}
                disabled={loading}
              />
            </label>
          ) : null}
        </div>
        <button type="submit" style={styles.button} disabled={loading}>
          {loading ? "Loading..." : "Load / Initialize"}
        </button>
      </form>
      <p style={styles.hint}>先初始化比赛（Series），然后可以直接用自然语言提问选手、战术或关键回合。</p>
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: "16px",
    background: "#fff",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    boxShadow: "0 2px 6px rgba(15, 23, 42, 0.06)",
  },
  headerRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "12px",
  },
  heading: {
    margin: 0,
  },
  badgeReady: {
    padding: "4px 8px",
    borderRadius: "999px",
    background: "#ecfdf3",
    color: "#16a34a",
    fontSize: "12px",
    border: "1px solid #bbf7d0",
  },
  badgeIdle: {
    padding: "4px 8px",
    borderRadius: "999px",
    background: "#f8fafc",
    color: "#334155",
    fontSize: "12px",
    border: "1px solid #e2e8f0",
  },
  form: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
    alignItems: "end",
  },
  advancedBox: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    fontSize: "12px",
    color: "#475569",
  },
  input: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
  },
  button: {
    padding: "12px 14px",
    borderRadius: "8px",
    border: "none",
    background: "#2563eb",
    color: "#fff",
    cursor: "pointer",
    fontWeight: 600,
  },
  toggle: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    background: "#f8fafc",
    color: "#0f172a",
    cursor: "pointer",
    fontWeight: 600,
    textAlign: "left" as const,
  },
  hint: {
    marginTop: "10px",
    color: "#475569",
    fontSize: "13px",
  },
};
