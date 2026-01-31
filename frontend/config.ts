export type RenderMode = "off" | "template" | "llm-contextual";

export const config = {
  renderMode: "llm-contextual" as RenderMode,
  defaultGameId: "valorant" as const,
  apiBase: "http://localhost:8000/api",
  llm: {
    model: "gpt-4o",
    timeoutMs: 4000,
    apiKey: (import.meta as any).env?.VITE_OPENAI_API_KEY || (import.meta as any).env?.OPENAI_API_KEY || "",
  },
};

export type RenderMode = typeof config.renderMode;