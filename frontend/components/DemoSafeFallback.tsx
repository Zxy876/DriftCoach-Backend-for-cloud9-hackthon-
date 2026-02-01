import React from "react";

type Props = {
  title?: string;
};

export function DemoSafeFallback({ title }: Props) {
  const lastNarrative =
    typeof window !== "undefined" ? (window as any).__DC_LAST_NARRATIVE__ : undefined;
  const lastAnswer = typeof window !== "undefined" ? (window as any).__DC_LAST_ANSWER__ : undefined;

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.heading}>{title || "渲染异常，已切换安全模式"}</h2>
      <p style={styles.text}>页面渲染遇到问题，但原始内容仍可查看。</p>
      {lastAnswer ? (
        <div style={styles.block}>
          <div style={styles.blockTitle}>Last Answer</div>
          <pre style={styles.pre}>{String(lastAnswer)}</pre>
        </div>
      ) : null}
      {lastNarrative ? (
        <div style={styles.block}>
          <div style={styles.blockTitle}>Last Narrative (raw)</div>
          <pre style={styles.pre}>{String(lastNarrative)}</pre>
        </div>
      ) : (
        <div style={styles.note}>暂无可用的 narrative 内容缓存。</div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    padding: "24px",
    background: "#fff7ed",
    color: "#431407",
    border: "1px solid #fed7aa",
    borderRadius: "12px",
    maxWidth: "960px",
    margin: "24px auto",
    boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
    fontFamily: "Inter, -apple-system, system-ui, sans-serif",
  },
  heading: {
    margin: 0,
    marginBottom: "8px",
    fontSize: "20px",
    fontWeight: 700,
  },
  text: {
    margin: 0,
    marginBottom: "12px",
    fontSize: "14px",
  },
  block: {
    marginTop: "12px",
    border: "1px solid #fed7aa",
    background: "#fffbeb",
    borderRadius: "8px",
    padding: "12px",
  },
  blockTitle: {
    fontWeight: 700,
    marginBottom: "6px",
    color: "#9a3412",
    fontSize: "13px",
  },
  pre: {
    margin: 0,
    whiteSpace: "pre-wrap",
    fontFamily: "Menlo, Consolas, monospace",
    fontSize: "12px",
    lineHeight: 1.5,
  },
  note: {
    marginTop: "6px",
    color: "#92400e",
    fontSize: "13px",
  },
};