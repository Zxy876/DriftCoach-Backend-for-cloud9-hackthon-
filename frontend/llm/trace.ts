export type ExplanationTrace = {
  traceId: string;
  intent: string;
  gameProfile: string;
  renderMode: "off" | "template" | "llm-contextual";
  sourceFields: string[];
  fallbackUsed: boolean;
  message?: string;
};

export function createTrace(params: Omit<ExplanationTrace, "traceId">): ExplanationTrace {
  const traceId = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return { traceId, ...params };
}