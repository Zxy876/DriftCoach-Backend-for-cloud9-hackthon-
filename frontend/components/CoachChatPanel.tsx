import { useState } from "react";
import type { InferencePlan } from "../types/context";

interface Props {
  loading?: boolean;
  assistantMessage?: string;
  inferencePlan?: InferencePlan;
  onSend: (query: string) => Promise<void> | void;
  disabled?: boolean;
}

export function CoachChatPanel({ loading, assistantMessage, inferencePlan, onSend, disabled }: Props) {
  const [text, setText] = useState("");

  const locked = loading || disabled || !onSend;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    await onSend(text.trim());
    setText("");
  }

  return (
    <section style={styles.container}>
      <h3 style={styles.heading}>Coach Chat</h3>
      <form onSubmit={handleSubmit} style={styles.form}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="仅输入自然语言，例如：他最近表现是否稳定？"
          style={styles.input}
          disabled={locked}
        />
        <button type="submit" style={styles.button} disabled={locked}>
          {loading ? "发送中..." : "Send"}
        </button>
      </form>
      {assistantMessage ? <div style={styles.message}>{assistantMessage}</div> : null}
      {inferencePlan ? (
        <div style={styles.planBox}>
          <div style={styles.planHeader}>
            判定：{inferencePlan.judgment} | 可信度备注：{inferencePlan.confidence_note}
          </div>
          <div style={styles.planText}>{inferencePlan.rationale}</div>
          {inferencePlan.missing_evidence && inferencePlan.missing_evidence.length > 0 ? (
            <ul style={styles.list}>
              {inferencePlan.missing_evidence.map((m, idx) => (
                <li key={idx}>
                  <strong>{m.concept}</strong> 需要 {m.required_entity}：{m.reason}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    marginTop: "20px",
    padding: "16px",
    background: "#fff",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    boxShadow: "0 2px 6px rgba(15, 23, 42, 0.06)",
  },
  heading: {
    margin: 0,
    marginBottom: "12px",
  },
  form: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
  },
  input: {
    flex: 1,
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
  },
  button: {
    padding: "10px 14px",
    borderRadius: "8px",
    border: "none",
    background: "#2563eb",
    color: "#fff",
    cursor: "pointer",
  },
  message: {
    marginTop: "12px",
    padding: "10px",
    borderRadius: "8px",
    background: "#f8fafc",
    color: "#0f172a",
    border: "1px solid #e2e8f0",
    whiteSpace: "pre-wrap",
  },
  planBox: {
    marginTop: "12px",
    padding: "10px",
    borderRadius: "8px",
    background: "#eff6ff",
    border: "1px solid #bfdbfe",
    color: "#0f172a",
    fontSize: "14px",
  },
  planHeader: {
    fontWeight: 600,
    marginBottom: "6px",
  },
  planText: {
    marginBottom: "6px",
  },
  list: {
    margin: 0,
    paddingLeft: "18px",
  },
};
