export type RenderMode = "off" | "template" | "llm-contextual";

const envApiBase = (import.meta as any).env?.VITE_API_BASE || (import.meta as any).env?.VITE_API_BASE_URL;
const envDemoMode = ((import.meta as any).env?.VITE_DEMO_MODE || "").toString().toLowerCase() === "true";

export const config = {
  renderMode: "llm-contextual" as RenderMode,
  defaultGameId: "valorant" as const,
  apiBase: envApiBase || "http://localhost:8000/api",
  demoMode: envDemoMode,
  llm: {
    model: "gpt-4o",
    timeoutMs: 4000,
    apiKey: (import.meta as any).env?.VITE_OPENAI_API_KEY || (import.meta as any).env?.OPENAI_API_KEY || "",
  },
};

export type RenderModeValue = typeof config.renderMode;