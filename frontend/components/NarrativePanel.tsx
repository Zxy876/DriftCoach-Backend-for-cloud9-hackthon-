import React from "react";

type NarrativePayload = {
  type?: string;
  confidence?: number | string | null;
  content?: unknown;
};

type Props = {
  narrative?: NarrativePayload | null;
};

function normalizeContent(raw: unknown): string {
  try {
    if (raw === null || raw === undefined) return "暂无 narrative 内容";
    if (typeof raw === "string") return raw.slice(0, 8000);
    if (Array.isArray(raw)) return JSON.stringify(raw, null, 2).slice(0, 8000);
    if (typeof raw === "object") {
      const obj = raw as any;
      if (typeof obj.markdown === "string") return obj.markdown.slice(0, 8000);
      if (Array.isArray(obj.sections)) {
        const sections = obj.sections
          .filter((s: any) => s)
          .map((s: any, idx: number) => {
            const title = s.title || `Section ${idx + 1}`;
            const body = typeof s.body === "string" ? s.body : JSON.stringify(s.body ?? "", null, 2);
            return `${title}\n${body}`;
          });
        if (sections.length > 0) return sections.join("\n\n").slice(0, 8000);
      }
      if (typeof obj.content === "string") return obj.content.slice(0, 8000);
      return JSON.stringify(raw, null, 2).slice(0, 8000);
    }
    return String(raw).slice(0, 8000);
  } catch (e) {
    return "Narrative 渲染失败，已启用安全模式。";
  }
}

export function NarrativePanel({ narrative }: Props) {
  const confidence = narrative?.confidence;
  const nType = narrative?.type || "unknown";
  const rawContent = (narrative as any)?.content ?? narrative;
  const text = normalizeContent(rawContent);

  return (
    <section style={styles.panel}>
      <div style={styles.header}>
        <h3 style={styles.title}>Narrative</h3>
        <div style={styles.meta}>
          <span>Type: {nType}</span>
          <span>Confidence: {confidence ?? "n/a"}</span>
        </div>
      </div>
      <div style={styles.body}>
        <pre style={styles.pre}>{text}</pre>
      </div>
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    marginTop: "16px",
    padding: "12px",
    border: "1px solid #e5e7eb",
    borderRadius: "10px",
    background: "#fff",
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
  },
  header: {
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
  meta: {
    display: "flex",
    gap: "12px",
    fontSize: "12px",
    color: "#475569",
  },
  body: {
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    background: "#f8fafc",
    padding: "10px",
  },
  pre: {
    margin: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontFamily: "Menlo, Consolas, monospace",
    fontSize: "13px",
    lineHeight: 1.6,
    color: "#0f172a",
  },
};