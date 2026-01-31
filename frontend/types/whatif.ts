export type Action = "SAVE" | "RETAKE" | "FORCE" | "ECO" | "CONTEST" | "TRADE";

export type WhatIfPayload = {
  win_prob: number | null; // null when insufficient support
  support: number; // sample size for this action
  insufficient_support?: boolean;
};

export type WhatIfOutcome = {
  state: string;
  actions: Action[];
  outcomes: Record<Action, WhatIfPayload>;
  confidence: number; // overall confidence 0-1
  explanation?: string; // optional LLM rendering
  explanationTrace?: import("../llm/trace").ExplanationTrace;
};
