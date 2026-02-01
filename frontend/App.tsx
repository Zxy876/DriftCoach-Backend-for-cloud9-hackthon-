import { useEffect, useState } from "react";
import { ContextHeader } from "./components/ContextHeader";
import { ContextSetup } from "./components/ContextSetup";
import { InsightPanel } from "./components/InsightPanel";
import { ReviewPanel } from "./components/ReviewPanel";
import { WhatIfPanel } from "./components/WhatIfPanel";
import { CoachChatPanel } from "./components/CoachChatPanel";
import { SessionAnalysisPanel } from "./components/SessionAnalysisPanel";
import { NarrativePanel } from "./components/NarrativePanel";
import type { CoachPayload, DemoPayload } from "./types/context";
import demo from "./mocks/demo.json";
import { renderInsight, renderReview, renderWhatIf } from "./llm/render";
import { config } from "./config";

type AnalysisPhase = "INIT_ONLY" | "QUERY_SENT" | "ANALYSIS_UPDATED" | "IDLE";

function extractNarrativeText(payload: any): string | null {
  const narrative = payload?.narrative;
  if (!narrative) return null;
  const content = narrative?.content ?? narrative;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) return JSON.stringify(content, null, 2);
  if (typeof content === "object") {
    if (typeof (content as any).markdown === "string") return (content as any).markdown;
    if (Array.isArray((content as any).sections)) {
      const sections = (content as any).sections
        .filter(Boolean)
        .map((s: any, idx: number) => `${s?.title || `Section ${idx + 1}`}` + (s?.body ? `\n${s.body}` : ""));
      if (sections.length > 0) return sections.join("\n\n");
    }
    return JSON.stringify(content, null, 2);
  }
  return String(content);
}

function cacheFallbackText(payload: CoachPayload | null) {
  if (typeof window === "undefined" || !payload) return;
  const narrativeText = extractNarrativeText(payload);
  if (narrativeText) (window as any).__DC_LAST_NARRATIVE__ = narrativeText;
  const answerText = (payload as any).assistant_message || (payload as any).answer_synthesis?.claim;
  if (answerText) (window as any).__DC_LAST_ANSWER__ = answerText;
}

export function App() {
  const [payload, setPayload] = useState<CoachPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [initLoading, setInitLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [contextLoaded, setContextLoaded] = useState<boolean>(false);
  const [phase, setPhase] = useState<AnalysisPhase>("IDLE");
  const renderMode = config.renderMode;

  useEffect(() => {
    if (config.apiBase.includes(":5173")) {
      console.warn(
        `API base appears to target the frontend dev server (5173): ${config.apiBase}. Update to the backend port (8000).`
      );
    }
  }, []);

  async function enrichPayload(source: CoachPayload): Promise<CoachPayload> {
    const enrichedInsights = Array.isArray(source.insights)
      ? await Promise.all(
          (source.insights || []).map(async (i) => {
            const rendered = await renderInsight(i, { mode: renderMode, gameId: config.defaultGameId });
            return { ...i, explanation: rendered.text, explanationTrace: rendered.trace };
          })
        )
      : [];

    const enrichedReview = Array.isArray(source.review)
      ? await Promise.all(
          (source.review || []).map(async (r) => {
            const rendered = await renderReview(r, { mode: renderMode, gameId: config.defaultGameId });
            return { ...r, explanation: rendered.text, explanationTrace: rendered.trace };
          })
        )
      : [];

    let renderedWhatIf: Awaited<ReturnType<typeof renderWhatIf>> | null = null;
    if (source.whatIf) {
      renderedWhatIf = await renderWhatIf(source.whatIf as any, { mode: renderMode, gameId: config.defaultGameId });
    }

    const enriched: CoachPayload = {
      ...(source as CoachPayload),
      insights: enrichedInsights,
      review: enrichedReview,
      whatIf: source.whatIf
        ? { ...(source as any).whatIf, explanation: renderedWhatIf?.text, explanationTrace: renderedWhatIf?.trace }
        : undefined,
    };

    cacheFallbackText(enriched);
    return enriched;
  }

  useEffect(() => {
    async function bootstrap() {
      let source: CoachPayload = demo as CoachPayload;
      setError(null);
      try {
        const resp = await fetch(`${config.apiBase}/demo`);
        const contentType = resp.headers.get("content-type") || "";
        if (!resp.ok) throw new Error(`API status ${resp.status}`);
        if (!contentType.includes("application/json")) throw new Error(`Unexpected content-type: ${contentType}`);
        const json = (await resp.json()) as CoachPayload;
        source = json;
      } catch (err) {
        console.warn("API fetch failed, fallback to mock", err);
        setError("API fetch failed, using mock demo");
      }

      const enriched = await enrichPayload(source);
      setPayload(enriched);
      cacheFallbackText(enriched);
      setPhase("INIT_ONLY");
    }

    void bootstrap();
  }, [renderMode]);

  async function handleCoachQuery(query: string) {
    if (!query) return;
    if (!contextLoaded) {
      setError("请先在 Context Setup 中完成 GRID 初始化");
      return;
    }
    if (/grid_[a-z_]*=|GRID_/i.test(query)) {
      setError("教练对话仅接受自然语言，不接受 ID 或 KV 字符串");
      return;
    }
    if (!sessionId) {
      setError("缺少会话 ID，请重新初始化 Context Setup");
      return;
    }
    const lastPlayerName = (payload as any)?.context?.meta?.last_player_name as string | undefined;
    setLoading(true);
    setError(null);
    setPhase("QUERY_SENT");
    try {
      const resp = await fetch(`${config.apiBase}/coach/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ coach_query: query, session_id: sessionId, last_player_name: lastPlayerName }),
      });

      if (!resp.ok) {
        showToast("后端返回异常，已启用安全模式");
        return;
      }

      const text = await resp.text();
      if (text.length > 200_000) {
        setPayload({
          narrative: {
            type: "TRUNCATED",
            content: text.slice(0, 8000),
            confidence: 0.1,
          },
        } as any);
        setPhase("QUERY_SENT");
        return;
      }

      const json = JSON.parse(text) as CoachPayload & { gate?: string; reasons?: string[]; answer_synthesis?: { claim?: string } };

      // Gate handling: evidence insufficient / llm disabled
      if ((json as any).gate === "EVIDENCE_INSUFFICIENT") {
        setPayload({ ...(json as any), assistant_message: "⚠️ 当前证据不足，分析未展开\n原因：" + ((json as any).reasons || []).join("; ") });
        setPhase("QUERY_SENT");
        return;
      }

      // AnswerSynthesis 优先展示；若不存在则判定为 INSUFFICIENT
      if (!(json as any).answer_synthesis) {
        const insufficientPayload = { ...(json as any), assistant_message: "当前问题证据不足（INSUFFICIENT）" } as CoachPayload;
        setPayload(insufficientPayload);
        cacheFallbackText(insufficientPayload);
        setPhase("QUERY_SENT");
        return;
      }

      const enriched = await enrichPayload(json);
      setPayload(enriched);
      cacheFallbackText(enriched);
      cacheFallbackText(enriched);

      const delta =
        (json.context?.evidence?.delta_by_type && Object.keys(json.context.evidence.delta_by_type).length > 0) ||
        (json.context?.evidence?.delta_states && json.context.evidence.delta_states > 0) ||
        (json.session_analysis?.recently_added_node_ids && json.session_analysis.recently_added_node_ids.length > 0);
      setPhase(delta ? "ANALYSIS_UPDATED" : "QUERY_SENT");
    } catch (err) {
      console.error("coach/query failed", err);
      setError("无法连接后端服务");
    } finally {
      setLoading(false);
    }
  }

  async function handleInit(_playerId: string | undefined, seriesId: string) {
    if (contextLoaded) return;
    setInitLoading(true);
    setError(null);
    try {
      const body: Record<string, string> = { grid_series_id: seriesId };
      const resp = await fetch(`${config.apiBase}/coach/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        if (resp.status === 429) {
          setError("数据接口限流，请稍后重试");
          return;
        }
        let detail = await resp.text();
        try {
          const parsed = JSON.parse(detail);
          detail = parsed.detail || detail;
        } catch (e) {
          // keep original detail
        }
        throw new Error(`INIT status ${resp.status}: ${detail}`);
      }
      const json = await resp.json();
      setSessionId(json.session_id);
      setContextLoaded(Boolean(json.context_loaded));
      setPhase("INIT_ONLY");
      if (json.context) {
        setPayload((prev) => (prev ? { ...prev, context: { ...prev.context, ...json.context } } : prev));
      }
    } catch (err) {
      console.error("coach/init failed", err);
      setError(err instanceof Error ? err.message : "coach/init failed");
      setContextLoaded(false);
    } finally {
      setInitLoading(false);
    }
  }

  if (!payload) {
    return <div style={styles.page}>Loading demo...</div>;
  }

  const deltaByType = payload.context?.evidence?.delta_by_type || {};
  const deltaStates = payload.context?.evidence?.delta_states || 0;
  const recentlyAdded = payload.session_analysis?.recently_added_node_ids || [];
  const isDemoMode = config.demoMode || Boolean((payload as any).context?.meta?.demo_mode);
  const demoRemaining = (payload as any).context?.meta?.demo_remaining_queries;
  const narrative = (payload as any).narrative;

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>DriftCoach Frontend Demo</h2>
      {isDemoMode ? (
        <div style={styles.badgeRow}>
          <span style={styles.demoBadge}>Demo Mode</span>
          {typeof demoRemaining === "number" ? <span style={styles.demoNote}>Remaining queries: {demoRemaining}</span> : null}
          <span style={styles.demoNote}>API: {config.apiBase}</span>
        </div>
      ) : null}
      <p style={styles.subtitle}>Demo flow (frozen order): 1) Player Insight → 2) Post-match Review → 3) What-if Analysis</p>
      {error ? <div style={styles.error}>{error}</div> : null}
      <ContextSetup onLoad={handleInit} loading={initLoading} contextLoaded={contextLoaded} />
      <ContextHeader context={payload.context} />
      <SessionAnalysisPanel analysis={payload.session_analysis} />
      <section style={styles.deltaBox}>
        <strong>本次新增分析 ({phase})</strong>
        <ul style={{ margin: 0, paddingLeft: "18px", color: "#0f172a", fontSize: "13px" }}>
          {deltaStates ? <li>delta_states: {deltaStates}</li> : null}
          {Object.keys(deltaByType).length > 0
            ? Object.entries(deltaByType).map(([k, v]) => (
                <li key={k}>
                  {k} × {v as any}
                </li>
              ))
            : null}
          {recentlyAdded.length > 0 ? <li>recently added nodes: {recentlyAdded.length}</li> : null}
          {deltaStates === 0 && Object.keys(deltaByType).length === 0 && recentlyAdded.length === 0 ? <li>暂无增量</li> : null}
        </ul>
      </section>
      <div style={styles.panels}>
        <InsightPanel insights={payload.insights} />
        <ReviewPanel review={payload.review} />
        <WhatIfPanel whatIf={payload.whatIf} />
      </div>
      <NarrativePanel narrative={narrative} />
      <CoachChatPanel
        loading={loading}
        assistantMessage={payload.assistant_message || (payload as any).answer_synthesis?.claim}
        inferencePlan={payload.inference_plan}
        onSend={handleCoachQuery}
        disabled={!contextLoaded}
      />
      <section style={styles.assumptions}>
        <strong>Assumptions & Limits（frozen, always visible）</strong>
        <ul style={{ margin: 0, paddingLeft: "20px" }}>
          <li>Based on similar historical states</li>
          <li>Signal strength: weak / moderate / strong</li>
          <li>This is not a recommendation</li>
        </ul>
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    fontFamily: "Inter, -apple-system, system-ui, sans-serif",
    padding: "24px",
    background: "#f5f7fb",
    color: "#0f172a",
  },
  heading: {
    marginTop: 0,
    marginBottom: "12px",
  },
  subtitle: {
    marginTop: 0,
    marginBottom: "12px",
    color: "#475569",
    fontSize: "14px",
  },
  badgeRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "8px",
  },
  demoBadge: {
    display: "inline-flex",
    alignItems: "center",
    padding: "4px 10px",
    background: "#0f172a",
    color: "#fff",
    borderRadius: "999px",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.2px",
  },
  demoNote: {
    fontSize: "12px",
    color: "#475569",
  },
  panels: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "16px",
    marginTop: "16px",
  },
  deltaBox: {
    marginBottom: "12px",
    padding: "12px",
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    background: "#f8fafc",
  },
  assumptions: {
    marginTop: "24px",
    border: "1px dashed #cbd5e1",
    borderRadius: "8px",
    padding: "12px",
    background: "#fff",
    fontSize: "14px",
  },
  error: {
    marginTop: "12px",
    padding: "10px",
    background: "#fef2f2",
    color: "#b91c1c",
    border: "1px solid #fecdd3",
    borderRadius: "8px",
  },
};
